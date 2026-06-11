def train():
    import prelude

    import logging
    import sys
    import os
    import gc
    import gzip
    import json
    import shutil
    import random
    import torch
    from os import path
    from glob import glob
    from datetime import datetime
    from itertools import chain
    from torch import optim, nn
    from torch.amp import GradScaler
    from torch.nn.utils import clip_grad_norm_
    from torch.utils.data import DataLoader
    from torch.utils.tensorboard import SummaryWriter
    from common import submit_param, parameter_count, drain, filtered_trimmed_lines, tqdm
    from player import TestPlayer
    from dataloader import FileDatasetsIter, worker_init_fn
    from lr_scheduler import LinearWarmUpCosineAnnealingLR
    from model import Brain, DQN, AuxNet
    from libriichi.consts import obs_shape
    from config import config

    version = config['control']['version']

    online = config['control']['online']
    batch_size = config['control']['batch_size']
    opt_step_every = config['control']['opt_step_every']
    save_every = config['control']['save_every']
    test_every = config['control']['test_every']
    submit_every = config['control']['submit_every']
    test_games = config['test_play']['games']
    min_q_weight = config['cql']['min_q_weight']
    next_rank_weight = config['aux']['next_rank_weight']
    # ── new aux task weights (default 0 → identical to old behavior) ────────
    shanten_aux_weight = config['aux'].get('shanten_weight', 0.0)
    houjuu_aux_weight  = config['aux'].get('houjuu_weight',  0.0)
    # ── new reward shaping weights ───────────────────────────────────────────
    shanten_shape_weight = config['env'].get('shanten_weight', 0.0)
    houjuu_shape_weight  = config['env'].get('houjuu_penalty', 0.0)
    # ── target network + n-step bootstrap (default off) ─────────────────────
    use_target_net = config['env'].get('use_target_net', False)
    target_tau     = config['env'].get('target_tau', 0.005)
    target_sync_every = config['env'].get('target_sync_every', 1)
    # ── distributional Q (QR-DQN). num_quantiles=1 → scalar Q (default) ─────
    num_quantiles = config['env'].get('num_quantiles', 1)
    assert save_every % opt_step_every == 0
    assert test_every % save_every == 0

    device = torch.device(config['control']['device'])
    torch.backends.cudnn.benchmark = config['control']['enable_cudnn_benchmark']
    enable_amp = config['control']['enable_amp']
    enable_compile = config['control']['enable_compile']

    pts = config['env']['pts']
    gamma = config['env']['gamma']
    file_batch_size = config['dataset']['file_batch_size']
    reserve_ratio = config['dataset']['reserve_ratio']
    num_workers = config['dataset']['num_workers']
    num_epochs = config['dataset']['num_epochs']
    enable_augmentation = config['dataset']['enable_augmentation']
    augmented_first = config['dataset']['augmented_first']
    eps = config['optim']['eps']
    betas = config['optim']['betas']
    weight_decay = config['optim']['weight_decay']
    max_grad_norm = config['optim']['max_grad_norm']

    mortal = Brain(version=version, **config['resnet']).to(device)
    dqn = DQN(version=version, num_quantiles=num_quantiles).to(device)
    # AuxNet outputs are concatenated heads. Old layout: (4,) for next-rank.
    # New layout: optionally append more heads. Order MUST match the loss.
    #   slot 0: next-rank logits (4 classes)         — always present
    #   slot 1: shanten regression (1 dim)           — if shanten_aux_weight > 0
    #   slot 2: houjuu probability logit (1 dim)     — if houjuu_aux_weight  > 0
    aux_dims = [4]
    if shanten_aux_weight > 0.0: aux_dims.append(1)
    if houjuu_aux_weight  > 0.0: aux_dims.append(1)
    aux_net = AuxNet(tuple(aux_dims)).to(device)
    all_models = (mortal, dqn, aux_net)

    # Target networks (only constructed when enabled to avoid memory cost).
    target_mortal = None
    target_dqn = None
    if use_target_net:
        import copy
        target_mortal = copy.deepcopy(mortal).eval().to(device)
        target_dqn = copy.deepcopy(dqn).eval().to(device)
        for p in target_mortal.parameters(): p.requires_grad_(False)
        for p in target_dqn.parameters():    p.requires_grad_(False)

    def _polyak_update(src, tgt, tau):
        with torch.no_grad():
            for ps, pt in zip(src.parameters(), tgt.parameters()):
                pt.data.mul_(1.0 - tau).add_(ps.data, alpha=tau)
            for bs, bt in zip(src.buffers(), tgt.buffers()):
                bt.data.copy_(bs.data)
    if enable_compile:
        for m in all_models:
            m.compile()

    logging.info(f'version: {version}')
    logging.info(f'obs shape: {obs_shape(version)}')
    logging.info(f'mortal params: {parameter_count(mortal):,}')
    logging.info(f'dqn params: {parameter_count(dqn):,}')
    logging.info(f'aux params: {parameter_count(aux_net):,}')

    mortal.freeze_bn(config['freeze_bn']['mortal'])

    decay_params = []
    no_decay_params = []
    for model in all_models:
        params_dict = {}
        to_decay = set()
        for mod_name, mod in model.named_modules():
            for name, param in mod.named_parameters(prefix=mod_name, recurse=False):
                params_dict[name] = param
                if isinstance(mod, (nn.Linear, nn.Conv1d)) and name.endswith('weight'):
                    to_decay.add(name)
        decay_params.extend(params_dict[name] for name in sorted(to_decay))
        no_decay_params.extend(params_dict[name] for name in sorted(params_dict.keys() - to_decay))
    param_groups = [
        {'params': decay_params, 'weight_decay': weight_decay},
        {'params': no_decay_params},
    ]
    optimizer = optim.AdamW(param_groups, lr=1, weight_decay=0, betas=betas, eps=eps)
    scheduler = LinearWarmUpCosineAnnealingLR(optimizer, **config['optim']['scheduler'])
    scaler = GradScaler(device.type, enabled=enable_amp)
    test_player = TestPlayer()
    best_perf = {
        'avg_rank': 4.,
        'avg_pt': -135.,
    }

    steps = 0
    state_file = config['control']['state_file']
    best_state_file = config['control']['best_state_file']
    if path.exists(state_file):
        state = torch.load(state_file, weights_only=True, map_location=device)
        timestamp = datetime.fromtimestamp(state['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        logging.info(f'loaded: {timestamp}')
        mortal.load_state_dict(state['mortal'])
        dqn.load_state_dict(state['current_dqn'])
        aux_net.load_state_dict(state['aux_net'])
        if not online or state['config']['control']['online']:
            optimizer.load_state_dict(state['optimizer'])
            scheduler.load_state_dict(state['scheduler'])
        scaler.load_state_dict(state['scaler'])
        best_perf = state['best_perf']
        steps = state['steps']

    optimizer.zero_grad(set_to_none=True)
    mse = nn.MSELoss()
    ce = nn.CrossEntropyLoss()

    if device.type == 'cuda':
        logging.info(f'device: {device} ({torch.cuda.get_device_name(device)})')
    else:
        logging.info(f'device: {device}')

    if online:
        submit_param(mortal, dqn, is_idle=True)
        logging.info('param has been submitted')

    writer = SummaryWriter(config['control']['tensorboard_dir'])
    stats = {
        'dqn_loss': 0,
        'cql_loss': 0,
        'next_rank_loss': 0,
        'shanten_aux_loss': 0,
        'houjuu_aux_loss': 0,
    }
    all_q = torch.zeros((save_every, batch_size), device=device, dtype=torch.float32)
    all_q_target = torch.zeros((save_every, batch_size), device=device, dtype=torch.float32)
    idx = 0

    def train_epoch():
        nonlocal steps
        nonlocal idx

        player_names = []
        if online:
            player_names = ['trainee']
            dirname = drain()
            file_list = list(map(lambda p: path.join(dirname, p), os.listdir(dirname)))
        else:
            player_names_set = set()
            for filename in config['dataset']['player_names_files']:
                with open(filename) as f:
                    player_names_set.update(filtered_trimmed_lines(f))
            player_names = list(player_names_set)
            logging.info(f'loaded {len(player_names):,} players')

            file_index = config['dataset']['file_index']
            if path.exists(file_index):
                index = torch.load(file_index, weights_only=True)
                file_list = index['file_list']
            else:
                logging.info('building file index...')
                file_list = []
                for pat in config['dataset']['globs']:
                    file_list.extend(glob(pat, recursive=True))
                if len(player_names_set) > 0:
                    filtered = []
                    for filename in tqdm(file_list, unit='file'):
                        with gzip.open(filename, 'rt') as f:
                            start = json.loads(next(f))
                            if not set(start['names']).isdisjoint(player_names_set):
                                filtered.append(filename)
                    file_list = filtered
                file_list.sort(reverse=True)
                torch.save({'file_list': file_list}, file_index)
        logging.info(f'file list size: {len(file_list):,}')

        before_next_test_play = (test_every - steps % test_every) % test_every
        logging.info(f'total steps: {steps:,} (~{before_next_test_play:,})')

        if num_workers > 1:
            random.shuffle(file_list)
        file_data = FileDatasetsIter(
            version = version,
            file_list = file_list,
            pts = pts,
            file_batch_size = file_batch_size,
            reserve_ratio = reserve_ratio,
            player_names = player_names,
            num_epochs = num_epochs,
            enable_augmentation = enable_augmentation,
            augmented_first = augmented_first,
            shanten_weight = shanten_shape_weight,
            houjuu_penalty = houjuu_shape_weight,
            emit_next = use_target_net,
            emit_aux_labels = (shanten_aux_weight > 0.0 or houjuu_aux_weight > 0.0),
        )
        data_loader = iter(DataLoader(
            dataset = file_data,
            batch_size = batch_size,
            drop_last = False,
            num_workers = num_workers,
            pin_memory = True,
            worker_init_fn = worker_init_fn,
        ))

        remaining = {k: [] for k in (
            'obs', 'actions', 'masks', 'steps_to_done',
            'kyoku_rewards', 'player_ranks',
            'intra_rewards', 'dones',
            'next_obs', 'next_masks',
        )}
        remaining_bs = 0
        pb = tqdm(total=save_every, desc='TRAIN', initial=steps % save_every)

        # Pre-compute quantile midpoints τ_i for QR-DQN loss.
        if num_quantiles > 1:
            taus = (torch.arange(num_quantiles, device=device, dtype=torch.float32) + 0.5) / num_quantiles
        else:
            taus = None

        def quantile_huber_loss(q_pred, q_target):
            """QR-DQN loss. q_pred (B, N), q_target (B, N)."""
            # td: (B, N_target, N_pred)  — pairs of all (target_j, pred_i)
            td = q_target.unsqueeze(-1) - q_pred.unsqueeze(1)
            # Huber κ=1
            huber = torch.where(td.abs() <= 1.0, 0.5 * td.pow(2), td.abs() - 0.5)
            tau = taus.view(1, 1, -1)                          # (1, 1, N_pred)
            weight = (tau - (td.detach() < 0).float()).abs()
            return (weight * huber).sum(dim=-1).mean()

        def train_batch(obs, actions, masks, steps_to_done, kyoku_rewards,
                        player_ranks, intra_rewards, dones,
                        next_obs=None, next_masks=None,
                        aux_shanten=None, aux_houjuu=None):
            nonlocal steps
            nonlocal idx
            nonlocal pb

            obs = obs.to(dtype=torch.float32, device=device)
            actions = actions.to(dtype=torch.int64, device=device)
            masks = masks.to(dtype=torch.bool, device=device)
            steps_to_done = steps_to_done.to(dtype=torch.int64, device=device)
            kyoku_rewards = kyoku_rewards.to(dtype=torch.float64, device=device)
            player_ranks = player_ranks.to(dtype=torch.int64, device=device)
            intra_rewards = intra_rewards.to(dtype=torch.float32, device=device)
            dones = dones.to(dtype=torch.bool, device=device)
            assert masks[range(batch_size), actions].all()

            # Reward target. Two routes:
            #   (a) MC return (default, online + offline both use this if
            #       use_target_net=False).
            #   (b) 1-step TD with target net + intra shaping (when enabled).
            if use_target_net:
                next_obs_t = next_obs.to(dtype=torch.float32, device=device)
                next_masks_t = next_masks.to(dtype=torch.bool, device=device)
                with torch.no_grad():
                    next_phi = target_mortal(next_obs_t)
                    next_q = target_dqn.expected_q(next_phi, next_masks_t)
                    next_v = next_q.amax(dim=-1)
                    # Reward at time t: kyoku contribution applies only at the
                    # final step of the kyoku, but we keep the original MC
                    # contract on terminal steps for stability.
                    base_r = intra_rewards
                    final_kyoku_r = kyoku_rewards.to(torch.float32) * dones.float()
                    r_t = base_r + final_kyoku_r
                    not_done = (~dones).float()
                    if num_quantiles > 1:
                        next_phi_dist = next_phi
                        # bootstrap with the per-quantile distribution of the
                        # greedy action under the target dueling head.
                        target_q_all = target_dqn(next_phi_dist, next_masks_t)  # (B, A, N)
                        a_star = target_q_all.mean(dim=-1).argmax(dim=-1)
                        bootstrap = target_q_all[range(batch_size), a_star]      # (B, N)
                        q_target = r_t.unsqueeze(-1) + gamma * not_done.unsqueeze(-1) * bootstrap
                    else:
                        q_target = r_t + gamma * not_done * next_v
                q_target = q_target.detach()
            else:
                q_target_mc = (gamma ** steps_to_done * kyoku_rewards).to(torch.float32)
                # Add intra shaping. It's already a per-step Δ-potential, so
                # adding it to the MC return is still potential-based overall
                # (adds Φ(s_T) - Φ(s_t) for the kyoku, telescoping).
                q_target_mc = q_target_mc + intra_rewards
                q_target = q_target_mc.detach()

            with torch.autocast(device.type, enabled=enable_amp):
                phi = mortal(obs)
                q_all = dqn(phi, masks)               # (B, A) or (B, A, N)
                if num_quantiles > 1:
                    q_a = q_all[range(batch_size), actions]                # (B, N)
                    if q_target.dim() == 1:
                        q_target = q_target.unsqueeze(-1).expand(-1, num_quantiles)
                    dqn_loss = quantile_huber_loss(q_a, q_target)
                    q_expected = q_all.mean(dim=-1)                        # for CQL
                    q_expected = q_expected.masked_fill(~masks, -torch.inf)
                    q_scalar = q_a.mean(dim=-1)
                else:
                    q_a = q_all[range(batch_size), actions]                # (B,)
                    dqn_loss = 0.5 * mse(q_a, q_target)
                    q_expected = q_all
                    q_scalar = q_a

                cql_loss = 0
                if not online:
                    cql_loss = q_expected.logsumexp(-1).mean() - q_scalar.mean()

                # ── Aux losses ──────────────────────────────────────────────
                aux_outputs = aux_net(phi)
                next_rank_logits = aux_outputs[0]
                next_rank_loss = ce(next_rank_logits, player_ranks)

                aux_extras = []
                aux_idx = 1
                shanten_aux_loss = torch.tensor(0.0, device=device)
                houjuu_aux_loss  = torch.tensor(0.0, device=device)
                if shanten_aux_weight > 0.0:
                    if aux_shanten is not None:
                        # 1-dim head: regress shanten in float.
                        pred = aux_outputs[aux_idx].squeeze(-1)
                        shanten_aux_loss = mse(pred, aux_shanten.to(device, dtype=torch.float32))
                        aux_extras.append(shanten_aux_loss * shanten_aux_weight)
                    aux_idx += 1
                if houjuu_aux_weight > 0.0:
                    if aux_houjuu is not None:
                        pred_logit = aux_outputs[aux_idx].squeeze(-1)
                        target = aux_houjuu.to(device, dtype=torch.float32)
                        houjuu_aux_loss = nn.functional.binary_cross_entropy_with_logits(
                            pred_logit, target
                        )
                        aux_extras.append(houjuu_aux_loss * houjuu_aux_weight)
                    aux_idx += 1

                loss = sum([
                    dqn_loss,
                    cql_loss * min_q_weight,
                    next_rank_loss * next_rank_weight,
                ] + aux_extras)
            scaler.scale(loss / opt_step_every).backward()

            with torch.inference_mode():
                stats['dqn_loss'] += dqn_loss
                if not online:
                    stats['cql_loss'] += cql_loss
                stats['next_rank_loss'] += next_rank_loss
                stats['shanten_aux_loss'] += shanten_aux_loss
                stats['houjuu_aux_loss'] += houjuu_aux_loss
                all_q[idx] = q_scalar.float()
                if q_target.dim() == 2:
                    all_q_target[idx] = q_target.mean(dim=-1).float()
                else:
                    all_q_target[idx] = q_target.float()

            steps += 1
            idx += 1
            if use_target_net and steps % target_sync_every == 0:
                _polyak_update(mortal, target_mortal, target_tau)
                _polyak_update(dqn,    target_dqn,    target_tau)
            if idx % opt_step_every == 0:
                if max_grad_norm > 0:
                    scaler.unscale_(optimizer)
                    params = chain.from_iterable(g['params'] for g in optimizer.param_groups)
                    clip_grad_norm_(params, max_grad_norm)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            scheduler.step()
            pb.update(1)

            if online and steps % submit_every == 0:
                submit_param(mortal, dqn, is_idle=False)
                logging.info('param has been submitted')

            if steps % save_every == 0:
                pb.close()

                # downsample to reduce tensorboard event size
                all_q_1d = all_q.cpu().numpy().flatten()[::128]
                all_q_target_1d = all_q_target.cpu().numpy().flatten()[::128]

                writer.add_scalar('loss/dqn_loss', stats['dqn_loss'] / save_every, steps)
                if not online:
                    writer.add_scalar('loss/cql_loss', stats['cql_loss'] / save_every, steps)
                writer.add_scalar('loss/next_rank_loss', stats['next_rank_loss'] / save_every, steps)
                if shanten_aux_weight > 0.0:
                    writer.add_scalar('loss/shanten_aux_loss', stats['shanten_aux_loss'] / save_every, steps)
                if houjuu_aux_weight > 0.0:
                    writer.add_scalar('loss/houjuu_aux_loss', stats['houjuu_aux_loss'] / save_every, steps)
                writer.add_scalar('hparam/lr', scheduler.get_last_lr()[0], steps)
                writer.add_histogram('q_predicted', all_q_1d, steps)
                writer.add_histogram('q_target', all_q_target_1d, steps)
                writer.flush()

                for k in stats:
                    stats[k] = 0
                idx = 0

                before_next_test_play = (test_every - steps % test_every) % test_every
                logging.info(f'total steps: {steps:,} (~{before_next_test_play:,})')

                state = {
                    'mortal': mortal.state_dict(),
                    'current_dqn': dqn.state_dict(),
                    'aux_net': aux_net.state_dict(),
                    'optimizer': optimizer.state_dict(),
                    'scheduler': scheduler.state_dict(),
                    'scaler': scaler.state_dict(),
                    'steps': steps,
                    'timestamp': datetime.now().timestamp(),
                    'best_perf': best_perf,
                    'config': config,
                }
                torch.save(state, state_file)

                if online and steps % submit_every != 0:
                    submit_param(mortal, dqn, is_idle=False)
                    logging.info('param has been submitted')

                if steps % test_every == 0:
                    stat = test_player.test_play(test_games // 4, mortal, dqn, device)
                    mortal.train()
                    dqn.train()

                    avg_pt = stat.avg_pt([90, 45, 0, -135]) # for display only, never used in training
                    better = avg_pt >= best_perf['avg_pt'] and stat.avg_rank <= best_perf['avg_rank']
                    if better:
                        past_best = best_perf.copy()
                        best_perf['avg_pt'] = avg_pt
                        best_perf['avg_rank'] = stat.avg_rank

                    logging.info(f'avg rank: {stat.avg_rank:.6}')
                    logging.info(f'avg pt: {avg_pt:.6}')
                    writer.add_scalar('test_play/avg_ranking', stat.avg_rank, steps)
                    writer.add_scalar('test_play/avg_pt', avg_pt, steps)
                    writer.add_scalars('test_play/ranking', {
                        '1st': stat.rank_1_rate,
                        '2nd': stat.rank_2_rate,
                        '3rd': stat.rank_3_rate,
                        '4th': stat.rank_4_rate,
                    }, steps)
                    writer.add_scalars('test_play/behavior', {
                        'agari': stat.agari_rate,
                        'houjuu': stat.houjuu_rate,
                        'fuuro': stat.fuuro_rate,
                        'riichi': stat.riichi_rate,
                    }, steps)
                    writer.add_scalars('test_play/agari_point', {
                        'overall': stat.avg_point_per_agari,
                        'riichi': stat.avg_point_per_riichi_agari,
                        'fuuro': stat.avg_point_per_fuuro_agari,
                        'dama': stat.avg_point_per_dama_agari,
                    }, steps)
                    writer.add_scalar('test_play/houjuu_point', stat.avg_point_per_houjuu, steps)
                    writer.add_scalar('test_play/point_per_round', stat.avg_point_per_round, steps)
                    writer.add_scalars('test_play/key_step', {
                        'agari_jun': stat.avg_agari_jun,
                        'houjuu_jun': stat.avg_houjuu_jun,
                        'riichi_jun': stat.avg_riichi_jun,
                    }, steps)
                    writer.add_scalars('test_play/riichi', {
                        'agari_after_riichi': stat.agari_rate_after_riichi,
                        'houjuu_after_riichi': stat.houjuu_rate_after_riichi,
                        'chasing_riichi': stat.chasing_riichi_rate,
                        'riichi_chased': stat.riichi_chased_rate,
                    }, steps)
                    writer.add_scalar('test_play/riichi_point', stat.avg_riichi_point, steps)
                    writer.add_scalars('test_play/fuuro', {
                        'agari_after_fuuro': stat.agari_rate_after_fuuro,
                        'houjuu_after_fuuro': stat.houjuu_rate_after_fuuro,
                    }, steps)
                    writer.add_scalar('test_play/fuuro_num', stat.avg_fuuro_num, steps)
                    writer.add_scalar('test_play/fuuro_point', stat.avg_fuuro_point, steps)
                    writer.flush()

                    if better:
                        torch.save(state, state_file)
                        logging.info(
                            'a new record has been made, '
                            f'pt: {past_best["avg_pt"]:.4} -> {best_perf["avg_pt"]:.4}, '
                            f'rank: {past_best["avg_rank"]:.4} -> {best_perf["avg_rank"]:.4}, '
                            f'saving to {best_state_file}'
                        )
                        shutil.copy(state_file, best_state_file)
                    if online:
                        # BUG: This is a bug with unknown reason. When training
                        # in online mode, the process will get stuck here. This
                        # is the reason why `main` spawns a sub process to train
                        # in online mode instead of going for training directly.
                        sys.exit(0)
                pb = tqdm(total=save_every, desc='TRAIN')

        def _expand_batch(t):
            """DataLoader yields tuples; collate them into either 8 or 10 tensors."""
            return t

        # Layout of every yielded sample (and therefore the collated batch):
        #   [obs, action, mask, steps_to_done, kyoku_rwd, player_rank,
        #    intra, done,
        #    (next_obs, next_mask)?,
        #    (aux_shanten, aux_houjuu)?]
        emit_aux = (shanten_aux_weight > 0.0 or houjuu_aux_weight > 0.0)
        for batch in data_loader:
            obs, actions, masks, steps_to_done, kyoku_rewards, player_ranks, intra_rewards, dones = batch[:8]
            cursor = 8
            if use_target_net:
                next_obs   = batch[cursor]
                next_masks = batch[cursor + 1]
                cursor += 2
            else:
                next_obs = next_masks = None
            if emit_aux:
                aux_shanten = batch[cursor]
                aux_houjuu  = batch[cursor + 1]
                cursor += 2
            else:
                aux_shanten = aux_houjuu = None
            bs = obs.shape[0]
            if bs != batch_size:
                remaining['obs'].append(obs)
                remaining['actions'].append(actions)
                remaining['masks'].append(masks)
                remaining['steps_to_done'].append(steps_to_done)
                remaining['kyoku_rewards'].append(kyoku_rewards)
                remaining['player_ranks'].append(player_ranks)
                remaining['intra_rewards'].append(intra_rewards)
                remaining['dones'].append(dones)
                if next_obs is not None:
                    remaining['next_obs'].append(next_obs)
                    remaining['next_masks'].append(next_masks)
                if aux_shanten is not None:
                    remaining.setdefault('aux_shanten', []).append(aux_shanten)
                    remaining.setdefault('aux_houjuu', []).append(aux_houjuu)
                remaining_bs += bs
                continue
            train_batch(
                obs, actions, masks, steps_to_done, kyoku_rewards,
                player_ranks, intra_rewards, dones,
                next_obs=next_obs, next_masks=next_masks,
                aux_shanten=aux_shanten, aux_houjuu=aux_houjuu,
            )

        remaining_batches = remaining_bs // batch_size
        if remaining_batches > 0:
            cat = lambda key: torch.cat(remaining[key], dim=0)
            obs           = cat('obs')
            actions       = cat('actions')
            masks         = cat('masks')
            steps_to_done = cat('steps_to_done')
            kyoku_rewards = cat('kyoku_rewards')
            player_ranks  = cat('player_ranks')
            intra_rewards = cat('intra_rewards')
            dones         = cat('dones')
            has_next = bool(remaining['next_obs'])
            next_obs   = cat('next_obs')   if has_next else None
            next_masks = cat('next_masks') if has_next else None
            has_aux = bool(remaining.get('aux_shanten'))
            aux_shanten_full = cat('aux_shanten') if has_aux else None
            aux_houjuu_full  = cat('aux_houjuu')  if has_aux else None
            start = 0
            end = batch_size
            while end <= remaining_bs:
                train_batch(
                    obs[start:end],
                    actions[start:end],
                    masks[start:end],
                    steps_to_done[start:end],
                    kyoku_rewards[start:end],
                    player_ranks[start:end],
                    intra_rewards[start:end],
                    dones[start:end],
                    next_obs=(next_obs[start:end] if has_next else None),
                    next_masks=(next_masks[start:end] if has_next else None),
                    aux_shanten=(aux_shanten_full[start:end] if has_aux else None),
                    aux_houjuu=(aux_houjuu_full[start:end] if has_aux else None),
                )
                start = end
                end += batch_size
        pb.close()

        if online:
            submit_param(mortal, dqn, is_idle=True)
            logging.info('param has been submitted')

    while True:
        train_epoch()
        gc.collect()
        # torch.cuda.empty_cache()
        # torch.cuda.synchronize()
        if not online:
            # only run one epoch for offline for easier control
            break

def main():
    import os
    import sys
    import time
    from subprocess import Popen
    from config import config

    # do not set this env manually
    is_sub_proc_key = 'MORTAL_IS_SUB_PROC'
    online = config['control']['online']
    if not online or os.environ.get(is_sub_proc_key, '0') == '1':
        train()
        return

    cmd = (sys.executable, __file__)
    env = {
        is_sub_proc_key: '1',
        **os.environ.copy(),
    }
    while True:
        child = Popen(
            cmd,
            stdin = sys.stdin,
            stdout = sys.stdout,
            stderr = sys.stderr,
            env = env,
        )
        if (code := child.wait()) != 0:
            sys.exit(code)
        time.sleep(3)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
