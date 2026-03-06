/**
 * API service — communicates with the orchestration backend.
 * Supports REST and WebSocket connections.
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_HOST = 'http://192.168.1.1:8000';
const WS_PATH = '/ws/telemetry';

class APIService {
  constructor() {
    this.baseURL = DEFAULT_HOST;
    this.ws = null;
    this._wsListeners = [];
    this._loadConfig();
  }

  async _loadConfig() {
    try {
      const host = await AsyncStorage.getItem('orchestrator_host');
      if (host) {
        this.baseURL = host;
        this._client = axios.create({ baseURL: this.baseURL, timeout: 10000 });
      }
    } catch (_) {}
    this._client = axios.create({ baseURL: this.baseURL, timeout: 10000 });
  }

  async setHost(host) {
    this.baseURL = host;
    await AsyncStorage.setItem('orchestrator_host', host);
    this._client = axios.create({ baseURL: host, timeout: 10000 });
    this.disconnectWS();
  }

  // ------------------------------------------------------------------
  // REST methods
  // ------------------------------------------------------------------

  async getStatus() {
    const r = await this._client.get('/api/v1/status');
    return r.data;
  }

  async listDevices() {
    const r = await this._client.get('/api/v1/devices');
    return r.data;
  }

  async getDevice(deviceId) {
    const r = await this._client.get(`/api/v1/devices/${deviceId}`);
    return r.data;
  }

  async registerDevice(device) {
    const r = await this._client.post('/api/v1/devices', device);
    return r.data;
  }

  async pingDevice(deviceId) {
    const r = await this._client.post(`/api/v1/devices/${deviceId}/ping`);
    return r.data;
  }

  async listAgents() {
    const r = await this._client.get('/api/v1/agents');
    return r.data;
  }

  async dispatchTask(agentId, task, params = {}, deviceId = null) {
    const r = await this._client.post('/api/v1/tasks', {
      agent_id: agentId,
      task,
      params,
      device_id: deviceId,
    });
    return r.data;
  }

  async broadcastTask(agentType, task, params = {}) {
    const r = await this._client.post('/api/v1/tasks/broadcast', {
      agent_type: agentType,
      task,
      params,
    });
    return r.data;
  }

  async buildFirmware(template = 'base', features = ['wifi'], version = null) {
    const r = await this._client.post('/api/v1/firmware/build', {
      template, features, version,
    });
    return r.data;
  }

  async optimiseDevice(deviceId) {
    const r = await this._client.post(`/api/v1/ai/optimise/${deviceId}`);
    return r.data;
  }

  async aiResearch(query, context = {}) {
    const r = await this._client.post('/api/v1/ai/research', { query, context });
    return r.data;
  }

  // ------------------------------------------------------------------
  // WebSocket
  // ------------------------------------------------------------------

  connectWS(onMessage) {
    const wsURL = this.baseURL.replace(/^http/, 'ws') + WS_PATH;
    this.ws = new WebSocket(wsURL);
    this.ws.onopen = () => console.log('[WS] Connected to', wsURL);
    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessage(data);
      } catch (_) {}
    };
    this.ws.onerror = (e) => console.warn('[WS] Error:', e.message);
    this.ws.onclose = () => console.log('[WS] Disconnected');
  }

  disconnectWS() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendWS(command, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command, ...payload }));
    }
  }
}

export default new APIService();
