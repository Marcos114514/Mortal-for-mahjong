# Mahjong RL Agent Demo

This folder contains the source code written for the IEMS5726AB project demo.
It wraps the Mortal mahjong agent source provided by the groupmate into a
submission-friendly application:

- one human player
- two random baseline agents
- one reinforcement-learning agent slot
- a Mortal CLI adapter when a trained Mortal checkpoint is available
- a deterministic Mortal-inspired fallback policy for demo and grading without
  shipping model weights

The original Mortal source code remains in `../Mortal-for-mahjong/Mortal`.
The course instruction says trained models should not be included in the ZIP/RAR,
so put the checkpoint download link in `application/model_link.txt` and keep the
actual `.pth` file outside the submission archive.

## Run The Browser Demo

Open:

```text
../application/index.html
```

No server is required. The demo implements a compact Japanese-mahjong-style draw
and discard loop with visible hands, discards, wall count, agent reasoning, and a
round log. It is designed for the short demonstration video.

## Optional Mortal Inference

If a Mortal checkpoint is available, copy
`../Mortal-for-mahjong/Mortal/mortal/config.example.toml` to
`../Mortal-for-mahjong/Mortal/mortal/config.toml`, then update:

```toml
[control]
state_file = "/absolute/path/to/mortal.best"
```

Then Mortal's documented CLI inference shape is:

```bash
cd ../Mortal-for-mahjong/Mortal/mortal
python mortal.py 0 < log.json
```

The Python adapter in `mahjong_agent/agent.py` can call that CLI and parse the
last JSON action. If the checkpoint or compiled `libriichi` dependency is not
available, it falls back to the heuristic policy so the application still runs.

## Project Mapping

- Data collection: Mortal supports mjai/Tenhou-style logs (`.json.gz`).
- Representation: game events are transformed into observation tensors and
  action masks inside `libriichi`.
- Modeling: Mortal uses a ResNet encoder plus DQN heads for action values.
- Deployment: this demo exposes the agent as a browser-playable game and keeps
  model inference replaceable through the CLI adapter.
