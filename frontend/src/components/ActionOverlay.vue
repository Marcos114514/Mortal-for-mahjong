<template>
  <div v-if="visible" class="action-overlay">
    <button v-if="cans?.can_ron_agari" class="act-btn act-ron" @click="emit('ron')">
      Ron
    </button>
    <button v-if="cans?.can_tsumo_agari" class="act-btn act-tsumo" @click="emit('tsumo')">
      Tsumo
    </button>
    <button v-if="cans?.can_riichi" class="act-btn act-riichi" @click="emit('riichi')">
      Riichi
    </button>
    <button v-if="cans?.can_pon" class="act-btn act-pon" @click="emit('pon')">
      Pon
    </button>
    <button v-if="cans?.can_chi_low" class="act-btn act-chi" @click="emit('chi', 'low')">
      Chi (low)
    </button>
    <button v-if="cans?.can_chi_mid" class="act-btn act-chi" @click="emit('chi', 'mid')">
      Chi (mid)
    </button>
    <button v-if="cans?.can_chi_high" class="act-btn act-chi" @click="emit('chi', 'high')">
      Chi (high)
    </button>
    <button v-if="cans?.can_pass" class="act-btn act-pass" @click="emit('pass')">
      Pass
    </button>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  cans: { type: Object, default: null },
});
const emit = defineEmits(["ron", "tsumo", "riichi", "pon", "chi", "pass"]);
</script>

<style scoped>
.action-overlay {
  position: absolute;
  bottom: 12%;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.78);
  border: 1px solid #444;
  border-radius: 8px;
  z-index: 50;
  pointer-events: auto;
}
.act-btn {
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid #555;
  background: #2a2a2a;
  color: #fff;
  transition: transform 0.08s, background 0.15s;
}
.act-btn:hover { background: #404040; transform: translateY(-2px); }
.act-ron     { background: #c0392b; border-color: #e74c3c; }
.act-tsumo   { background: #c0392b; border-color: #e74c3c; }
.act-riichi  { background: #b8860b; border-color: #ffd700; }
.act-pon     { background: #2a4d8c; border-color: #4a7ad9; }
.act-chi     { background: #2a8c4d; border-color: #4ad97a; }
.act-pass    { background: #555; border-color: #777; }
</style>
