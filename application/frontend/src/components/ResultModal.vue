<template>
  <div v-if="state" class="modal-backdrop" @click.self="onBackdropClick">
    <div class="modal-card">
      <h2 class="modal-title">{{ state.title }}</h2>

      <!-- Per-kyoku result: show point deltas + new totals -->
      <table v-if="state.kind === 'kyoku'" class="modal-table">
        <thead>
          <tr>
            <th>Seat</th>
            <th>Δ</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(name, i) in state.names" :key="i">
            <td class="t-name">{{ name }}</td>
            <td class="t-delta" :class="deltaClass(state.deltas[i])">
              {{ formatDelta(state.deltas[i]) }}
            </td>
            <td class="t-score">{{ state.scores[i] }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Game-over: final ranking -->
      <ol v-if="state.kind === 'game'" class="modal-ranking">
        <li v-for="(r, idx) in state.ranking" :key="r.i" :class="`rank-${idx+1}`">
          <span class="rank-pos">{{ idx + 1 }}.</span>
          <span class="rank-name">{{ r.name }}</span>
          <span class="rank-score">{{ r.score }}</span>
        </li>
      </ol>

      <div class="modal-buttons">
        <button class="m-btn m-btn-primary" @click="emit('continue')">
          {{ state.kind === "game" ? "New Game" : "Continue" }}
        </button>
        <button class="m-btn m-btn-secondary" @click="emit('quit')">
          Quit
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  state: { type: Object, default: null },
});
const emit = defineEmits(["continue", "quit"]);

function deltaClass(d) {
  if (d > 0) return "pos";
  if (d < 0) return "neg";
  return "";
}

function formatDelta(d) {
  if (d === 0) return "±0";
  return (d > 0 ? "+" : "") + d;
}

function onBackdropClick() {
  // Don't dismiss on backdrop click — force a button choice.
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.modal-card {
  min-width: 360px;
  max-width: 480px;
  background: #161616;
  border: 1px solid #3a3a3a;
  border-radius: 10px;
  padding: 28px 32px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.6);
  color: #eee;
}
.modal-title {
  margin: 0 0 18px 0;
  font-size: 20px;
  font-weight: 700;
  color: #ffd700;
  text-align: center;
}
.modal-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 22px;
}
.modal-table th {
  text-align: left;
  font-weight: 600;
  color: #888;
  padding: 6px 0;
  border-bottom: 1px solid #2a2a2a;
}
.modal-table td {
  padding: 8px 0;
  border-bottom: 1px solid #1a1a1a;
}
.t-name { color: #ddd; }
.t-delta { text-align: right; font-family: monospace; font-weight: 600; }
.t-delta.pos { color: #4ad97a; }
.t-delta.neg { color: #e74c3c; }
.t-score { text-align: right; font-family: monospace; color: #ccc; }

.modal-ranking {
  list-style: none;
  padding: 0;
  margin: 0 0 22px 0;
}
.modal-ranking li {
  display: grid;
  grid-template-columns: 30px 1fr auto;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  background: #1f1f1f;
  font-size: 14px;
}
.rank-pos { color: #888; font-weight: 700; }
.rank-name { color: #eee; }
.rank-score { color: #ffd700; font-family: monospace; font-weight: 600; }
.rank-1 { background: linear-gradient(90deg, #3a2f0a, #1f1f1f); border: 1px solid #ffd700; }
.rank-1 .rank-pos { color: #ffd700; }
.rank-2 { background: linear-gradient(90deg, #2c2c2c, #1f1f1f); border: 1px solid #c0c0c0; }
.rank-3 { background: linear-gradient(90deg, #2a1810, #1f1f1f); border: 1px solid #cd7f32; }

.modal-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.m-btn {
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: filter 0.12s;
}
.m-btn:hover { filter: brightness(1.15); }
.m-btn-primary { background: #1c5a2e; border-color: #2d8045; color: #fff; }
.m-btn-secondary { background: #2a2a2a; border-color: #555; color: #ddd; }
</style>
