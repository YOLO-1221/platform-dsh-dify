<script setup>
defineProps({
  windowStyle: { type: Object, default: () => ({ left: '0%', width: '100%' }) },
})

defineEmits(['seek'])
</script>

<template>
  <div class="overview-wrap">
    <span class="overview-label">全览</span>
    <div class="overview-track" @click="$emit('seek', $event)">
      <div class="overview-bg" />
      <div class="overview-window" :style="windowStyle" />
    </div>
  </div>
</template>

<style scoped>
.overview-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 10px;
  border-top: 1px solid var(--border-color-soft);
  flex-shrink: 0;
}

.overview-label {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.overview-track {
  position: relative;
  flex: 1;
  height: 22px;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
}

.overview-bg {
  position: absolute;
  inset: 0;
  background: rgba(148, 163, 184, 0.15);
}

.overview-window {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(64, 158, 255, 0.22);
  border: 1px solid rgba(64, 158, 255, 0.55);
  border-radius: 3px;
  pointer-events: none;
  box-sizing: border-box;
}
</style>
