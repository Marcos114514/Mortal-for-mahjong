import torch
import numpy as np

class RewardCalculator:
    """Compute per-step reward from game logs.

    Two layers:
      1. Kyoku-level (default): Δ expected-rank-utility predicted by GRP.
         This is potential-based (Ng/Harada/Russell 1999) so it does NOT
         change the optimal policy.
      2. Optional intra-kyoku shaping (potential-based as well):
         Φ(s) = -shanten_weight * shanten(s)
         shaped_r_t = γ · Φ(s_{t+1}) - Φ(s_t)
         A small extra penalty fires on a houjuu (deal-in) step.

    All shaping weights default to 0 → identical to the original behavior.
    """

    def __init__(
        self,
        grp=None,
        pts=None,
        uniform_init=False,
        *,
        shanten_weight=0.0,
        houjuu_penalty=0.0,
        gamma=1.0,
    ):
        self.device = torch.device('cpu')
        self.grp = grp.to(self.device).eval()
        self.uniform_init = uniform_init

        pts = pts or [3, 1, -1, -3]
        self.pts = torch.tensor(pts, dtype=torch.float64, device=self.device)
        self.shanten_weight = float(shanten_weight)
        self.houjuu_penalty = float(houjuu_penalty)
        self.gamma = float(gamma)

    # ─────────────────── kyoku-level (unchanged) ────────────────────────────

    def calc_grp(self, grp_feature):
        seq = list(map(
            lambda idx: torch.as_tensor(grp_feature[:idx+1], device=self.device),
            range(len(grp_feature)),
        ))

        with torch.inference_mode():
            logits = self.grp(seq)
        matrix = self.grp.calc_matrix(logits)
        return matrix

    def calc_rank_prob(self, player_id, grp_feature, rank_by_player):
        matrix = self.calc_grp(grp_feature)

        final_ranking = torch.zeros((1, 4), device=self.device)
        final_ranking[0, rank_by_player[player_id]] = 1.
        rank_prob = torch.cat((matrix[:, player_id], final_ranking))
        if self.uniform_init:
            rank_prob[0, :] = 1 / 4
        return rank_prob

    def calc_delta_pt(self, player_id, grp_feature, rank_by_player):
        rank_prob = self.calc_rank_prob(player_id, grp_feature, rank_by_player)
        exp_pts = rank_prob @ self.pts
        reward = exp_pts[1:] - exp_pts[:-1]
        return reward.cpu().numpy()

    def calc_delta_points(self, player_id, grp_feature, final_scores):
        seq = np.concatenate((grp_feature[:, 3 + player_id] * 1e4, [final_scores[player_id]]))
        delta_points = seq[1:] - seq[:-1]
        return delta_points

    # ─────────────────── intra-kyoku shaping (new) ──────────────────────────

    def calc_intra_shaping(self, shantens, dones, apply_gamma):
        """Return per-step shaping reward Δ-shanten as a numpy array.

        Args:
            shantens: list/array of int8, shanten count at each step (>= -1).
            dones: list/array of bool, True if the step is the LAST step of a
                kyoku (terminal). At the kyoku boundary we zero the diff to
                avoid leaking shanten across kyoku.
            apply_gamma: list/array of bool, mirrors the libriichi flag — only
                discard/kan steps "consume time" (γ applies). Other steps
                inherit Φ unchanged → diff is 0 by construction.
        Returns:
            np.ndarray of length len(shantens), float32.
        """
        if self.shanten_weight == 0.0:
            return np.zeros(len(shantens), dtype=np.float32)

        s = np.asarray(shantens, dtype=np.float32)
        # Clamp -1 (tenpai-after-agari sentinel) to -1 so Φ is well defined.
        s = np.clip(s, -1, 8)
        phi = -self.shanten_weight * s

        out = np.zeros(len(s), dtype=np.float32)
        # r_t = γ Φ(s_{t+1}) - Φ(s_t), zeroed at kyoku boundary.
        for t in range(len(s) - 1):
            if dones[t]:
                continue
            out[t] = self.gamma * phi[t + 1] - phi[t]
        return out

    def add_houjuu_penalty(self, rewards, houjuu_steps):
        if self.houjuu_penalty == 0.0 or not len(houjuu_steps):
            return rewards
        rewards = rewards.copy()
        for t in houjuu_steps:
            rewards[t] -= self.houjuu_penalty
        return rewards
