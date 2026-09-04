<template>
  <div v-if="isOpen" class="modal-backdrop" @click.self="emit('close')">
    <div class="modal-card glass-panel">
      <div class="modal-header">
        <h3>IBKR & Engine Settings</h3>
        <button class="btn-close" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <!-- Mode Switcher -->
        <div class="form-group">
          <label>Data Provider Engine</label>
          <div class="mode-selector">
            <button 
              type="button"
              class="btn-mode" 
              :class="{ active: form.useMock }" 
              @click="form.useMock = true"
            >
              High-Speed Simulator (No TWS required)
            </button>
            <button 
              type="button"
              class="btn-mode" 
              :class="{ active: !form.useMock }" 
              @click="form.useMock = false"
            >
              Interactive Brokers (TWS / Gateway)
            </button>
          </div>
        </div>

        <div v-if="!form.useMock" class="ibkr-fields">
          <div class="form-row">
            <div class="form-group flex-1">
              <label>Host</label>
              <input type="text" v-model="form.host" class="input-field mono" />
            </div>
            <div class="form-group flex-1">
              <label>Port (7497: Paper, 7496: Live, 4002: GW)</label>
              <input type="number" v-model.number="form.port" class="input-field mono" />
            </div>
          </div>

          <div class="form-group">
            <label>Client ID</label>
            <input type="number" v-model.number="form.clientId" class="input-field mono" />
          </div>

          <div class="info-box">
            <strong>TWS Configuration Checklist:</strong>
            <ul>
              <li>Enable ActiveX and Socket Clients in Global Configuration → API</li>
              <li>Ensure 'Socket port' matches above (default 7497 or 4002)</li>
              <li>Ensure 'Allow connections from localhost only' is checked</li>
            </ul>
          </div>
        </div>

        <div v-if="store.status.error" class="error-box mono">
          {{ store.status.error }}
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="emit('close')">Cancel</button>
        <button class="btn-save" @click="saveAndConnect">Save & Connect</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue';
import { useMarketStore } from '../stores/marketStore';

const props = defineProps({
  isOpen: Boolean
});
const emit = defineEmits(['close']);

const store = useMarketStore();

const form = reactive({
  host: store.status.host || '127.0.0.1',
  port: store.status.port || 4002,
  clientId: store.status.clientId || 1,
  useMock: store.status.isMock ?? false
});

watch(() => props.isOpen, (val) => {
  if (val) {
    form.host = store.status.host || '127.0.0.1';
    form.port = store.status.port || 4002;
    form.clientId = store.status.clientId || 1;
    form.useMock = store.status.isMock ?? false;
  }
});

function saveAndConnect() {
  store.connectIBKR({
    host: form.host,
    port: form.port,
    clientId: form.clientId,
    useMock: form.useMock
  });
  emit('close');
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 90%;
  max-width: 500px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.6);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  font-size: 16px;
  font-weight: 700;
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.mode-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-mode {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 10px 14px;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.btn-mode.active {
  background: rgba(37, 99, 235, 0.15);
  border-color: var(--accent-blue);
  color: #fff;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.input-field {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.input-field:focus {
  border-color: var(--accent-blue);
}

.info-box {
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.2);
  border-radius: 6px;
  padding: 12px;
  font-size: 11px;
  color: var(--text-secondary);
}

.info-box strong {
  color: var(--accent-cyan);
  display: block;
  margin-bottom: 6px;
}

.info-box ul {
  padding-left: 16px;
  line-height: 1.5;
}

.error-box {
  background: rgba(255, 59, 86, 0.1);
  border: 1px solid var(--red-ask);
  color: var(--red-ask);
  padding: 10px;
  border-radius: 6px;
  font-size: 12px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.btn-cancel {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.btn-save {
  background: var(--accent-blue);
  border: none;
  color: #fff;
  padding: 8px 18px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: opacity 0.2s ease;
}
.btn-save:hover {
  opacity: 0.9;
}
</style>
