<template>
  <aside class="panel">
    <div class="p-sec">
      <button @click="emit('newRound')">New Round</button>
      <button :disabled="!cans?.can_discard" @click="emit('autoDiscard')">Auto Discard</button>
    </div>
    <div class="p-sec">
      <div class="turn-row">
        <span :class="{ on: turn === 0 }">You</span>
        <span :class="{ on: turn === 1 }">P1</span>
        <span :class="{ on: turn === 2 }">Mortal</span>
        <span :class="{ on: turn === 3 }">P3</span>
      </div>
      <p v-if="hint" class="turn-hint">{{ hint }}</p>
    </div>
    <div class="p-sec">
      <h4>Agent Decision</h4>
      <p class="decision">{{ decisionText }}</p>
      <div class="q-list">
        <div v-for="row in rankedValues" :key="row.tile" class="q-row">
          <span class="qt">{{ row.tile }}</span>
          <span class="qb"><span :style="{ width: row.width + '%' }"></span></span>
          <span class="qv">{{ row.value.toFixed(1) }}</span>
        </div>
      </div>
    </div>
    <div class="p-sec log-sec">
      <h4>Log</h4>
      <pre class="log">{{ logMessages.slice(-14).join('\n') }}</pre>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  turn: { type: Number, default: 0 },
  cans: { type: Object, default: null },
  hint: { type: String, default: "" },
  decisionText: { type: String, default: "" },
  rankedValues: { type: Array, default: () => [] },
  logMessages: { type: Array, default: () => [] },
});
const emit = defineEmits(["newRound", "autoDiscard"]);
</script>

<style scoped>
.panel { grid-column: 2; background: #0f0f0f; border-left: 1px solid #222; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; font-size: 11px; }
.p-sec { border-bottom: 1px solid #1a1a1a; padding-bottom: 8px; }
.p-sec h4 { font-size: 9px; text-transform: uppercase; color: #555; margin-bottom: 4px; letter-spacing: 0.5px; }
button { padding: 5px 12px; background: #1c3a2a; border: 1px solid #2d6b4a; color: #eee; border-radius: 3px; cursor: pointer; font-size: 10px; margin-right: 5px; }
button:hover { background: #2d6b4a; }
button:disabled { opacity: 0.3; cursor: default; }
.turn-row { display: flex; gap: 5px; }
.turn-row span { padding: 2px 6px; border-radius: 3px; color: #555; font-size: 10px; }
.turn-row span.on { background: #2a2a16; color: #ffd700; font-weight: bold; }
.turn-hint { font-size: 11px; color: #ffd700; margin-top: 6px; font-weight: 600; }
.decision { color: #ffd700; font-size: 14px; font-weight: bold; margin: 4px 0 8px; }
.q-list { display: flex; flex-direction: column; gap: 3px; }
.q-row { display: grid; grid-template-columns: 28px 1fr 30px; align-items: center; gap: 4px; font-size: 9px; }
.qt { font-weight: bold; font-family: monospace; }
.qb { height: 5px; background: #1a1a1a; border-radius: 3px; overflow: hidden; }
.qb span { display: block; height: 100%; background: linear-gradient(90deg, #c0392b, #e74c3c); }
.qv { text-align: right; color: #666; font-family: monospace; }
.log-sec { flex: 1; min-height: 0; }
.log { font-family: 'Courier New', monospace; font-size: 9px; color: #777; white-space: pre-wrap; max-height: 200px; overflow-y: auto; background: #080808; padding: 6px; border-radius: 3px; }
</style>
