/**
 * Frequency Control Screen
 * Fine-tune, lock, scan, and visualise frequency data for selected devices
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert,
} from 'react-native';
import API from '../services/api';

const BANDS = ['2.4GHz', '5GHz', '915MHz', '868MHz', '433MHz'];
const PRESETS = [
  { label: '2.4 GHz WiFi ch1', hz: 2412000000 },
  { label: '2.4 GHz WiFi ch6', hz: 2437000000 },
  { label: '2.4 GHz WiFi ch11', hz: 2462000000 },
  { label: '5 GHz WiFi ch36', hz: 5180000000 },
  { label: '915 MHz LoRa', hz: 915000000 },
];

export default function FrequencyScreen() {
  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);
  const [agents, setAgents] = useState([]);
  const [freqAgentId, setFreqAgentId] = useState(null);
  const [targetHz, setTargetHz] = useState('2412000000');
  const [scanBand, setScanBand] = useState('2.4GHz');
  const [scanResults, setScanResults] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [locking, setLocking] = useState(false);
  const [tuning, setTuning] = useState(false);

  useEffect(() => {
    const init = async () => {
      const [devs, agts] = await Promise.all([API.listDevices(), API.listAgents()]);
      setDevices(devs);
      if (devs.length > 0) setSelectedDeviceId(devs[0].device_id);
      const fa = agts.find((a) => a.agent_type === 'frequency_agent');
      if (fa) setFreqAgentId(fa.agent_id);
      setAgents(agts);
    };
    init().catch(console.warn);
  }, []);

  const dispatch = (task, params) => {
    if (!freqAgentId) { Alert.alert('Error', 'No frequency agent found'); return null; }
    return API.dispatchTask(freqAgentId, task, params, selectedDeviceId);
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResults([]);
    try {
      await dispatch('scan', { band: scanBand });
      Alert.alert('Scan', `Band scan for ${scanBand} dispatched`);
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setScanning(false);
    }
  };

  const handleLock = async () => {
    const hz = parseFloat(targetHz);
    if (isNaN(hz)) { Alert.alert('Validation', 'Enter a valid frequency in Hz'); return; }
    setLocking(true);
    try {
      await dispatch('lock', { target_hz: hz });
      Alert.alert('Lock', `Lock to ${(hz / 1e6).toFixed(3)} MHz dispatched`);
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLocking(false);
    }
  };

  const handleFineTune = async () => {
    setTuning(true);
    try {
      await dispatch('fine_tune', { step_hz: 500000, iterations: 5 });
      Alert.alert('Fine-Tune', 'Adaptive fine-tune dispatched');
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setTuning(false);
    }
  };

  const handleFleetSync = async () => {
    const hz = parseFloat(targetHz);
    if (isNaN(hz)) { Alert.alert('Validation', 'Enter target frequency in Hz'); return; }
    try {
      await API.broadcastTask('frequency_agent', 'sync_fleet', { target_hz: hz });
      Alert.alert('Sync', `Fleet sync to ${(hz / 1e6).toFixed(3)} MHz dispatched`);
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      {/* Device selector */}
      <Text style={styles.label}>Target Device</Text>
      <View style={styles.pickerWrap}>
        {devices.map((d) => (
          <TouchableOpacity
            key={d.device_id}
            style={[styles.chip, selectedDeviceId === d.device_id && styles.chipActive]}
            onPress={() => setSelectedDeviceId(d.device_id)}
          >
            <Text style={[styles.chipText, selectedDeviceId === d.device_id && styles.chipTextActive]}>
              {d.name}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Frequency presets */}
      <Text style={styles.label}>Frequency Presets</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
        {PRESETS.map((p) => (
          <TouchableOpacity
            key={p.hz}
            style={styles.preset}
            onPress={() => setTargetHz(String(p.hz))}
          >
            <Text style={styles.presetLabel}>{p.label}</Text>
            <Text style={styles.presetHz}>{(p.hz / 1e6).toFixed(0)} MHz</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Manual frequency input */}
      <Text style={styles.label}>Target Frequency (Hz)</Text>
      <TextInput
        style={styles.input}
        value={targetHz}
        onChangeText={setTargetHz}
        keyboardType="numeric"
        placeholder="e.g. 2412000000"
      />

      {/* Actions */}
      <View style={styles.btnRow}>
        <ActionButton
          label={locking ? 'Locking…' : '🔒 Lock'}
          onPress={handleLock}
          disabled={locking}
        />
        <ActionButton
          label={tuning ? 'Tuning…' : '🎯 Fine-Tune'}
          onPress={handleFineTune}
          disabled={tuning}
          secondary
        />
      </View>

      <ActionButton label="⚡ Fleet Sync" onPress={handleFleetSync} wide />

      {/* Band scan */}
      <Text style={styles.sectionHeader}>Band Scan</Text>
      <View style={styles.pickerWrap}>
        {BANDS.map((b) => (
          <TouchableOpacity
            key={b}
            style={[styles.chip, scanBand === b && styles.chipActive]}
            onPress={() => setScanBand(b)}
          >
            <Text style={[styles.chipText, scanBand === b && styles.chipTextActive]}>{b}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <ActionButton
        label={scanning ? 'Scanning…' : `📡 Scan ${scanBand}`}
        onPress={handleScan}
        disabled={scanning}
        wide
      />
    </ScrollView>
  );
}

function ActionButton({ label, onPress, disabled, secondary, wide }) {
  return (
    <TouchableOpacity
      style={[
        styles.btn,
        secondary && styles.btnSecondary,
        wide && styles.btnWide,
        disabled && styles.btnDisabled,
      ]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text style={[styles.btnText, secondary && styles.btnSecondaryText]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  label: { fontSize: 12, fontWeight: '700', color: '#555', marginBottom: 6, textTransform: 'uppercase' },
  sectionHeader: { fontSize: 14, fontWeight: '700', color: '#333', marginTop: 20, marginBottom: 8 },
  pickerWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 16, borderWidth: 1, borderColor: '#0066CC',
  },
  chipActive: { backgroundColor: '#0066CC' },
  chipText: { fontSize: 12, color: '#0066CC' },
  chipTextActive: { color: '#fff' },
  preset: {
    backgroundColor: '#fff', borderRadius: 8, padding: 10,
    marginRight: 8, minWidth: 110, alignItems: 'center', elevation: 1,
  },
  presetLabel: { fontSize: 11, color: '#555' },
  presetHz: { fontSize: 14, fontWeight: '700', color: '#0066CC', marginTop: 2 },
  input: {
    backgroundColor: '#fff', borderRadius: 8,
    borderWidth: 1, borderColor: '#ddd', padding: 10,
    fontSize: 14, marginBottom: 12,
  },
  btnRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  btn: {
    flex: 1, backgroundColor: '#0066CC', borderRadius: 8,
    padding: 12, alignItems: 'center', marginBottom: 8,
  },
  btnSecondary: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#0066CC' },
  btnWide: { width: '100%', flex: undefined },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  btnSecondaryText: { color: '#0066CC' },
});
