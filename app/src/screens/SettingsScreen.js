/**
 * Settings Screen — configure orchestrator host, cloud endpoint, and app preferences
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TextInput,
  TouchableOpacity, Alert, Switch,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import API from '../services/api';
import COLORS from '../theme';

export default function SettingsScreen() {
  const [host, setHost] = useState('http://192.168.1.1:8000');
  const [cloudEndpoint, setCloudEndpoint] = useState('');
  const [liveUpdates, setLiveUpdates] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = async () => {
      const h = await AsyncStorage.getItem('orchestrator_host');
      if (h) setHost(h);
      const ce = await AsyncStorage.getItem('cloud_endpoint');
      if (ce) setCloudEndpoint(ce);
      const lu = await AsyncStorage.getItem('live_updates');
      if (lu !== null) setLiveUpdates(lu === 'true');
    };
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await API.setHost(host);
      await AsyncStorage.setItem('cloud_endpoint', cloudEndpoint);
      await AsyncStorage.setItem('live_updates', String(liveUpdates));
      Alert.alert('Saved', 'Settings saved successfully');
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      const status = await API.getStatus();
      Alert.alert(
        'Connection OK',
        `Orchestrator running: ${status.running}\nAgents: ${status.agents?.length ?? 0}\nDevices: ${status.devices?.length ?? 0}`,
      );
    } catch (e) {
      Alert.alert('Connection Failed', e.message);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.sectionHeader}>Orchestrator</Text>

      <Text style={styles.label}>Host URL</Text>
      <TextInput
        style={styles.input}
        value={host}
        onChangeText={setHost}
        placeholder="http://192.168.1.1:8000"
        placeholderTextColor={COLORS.textMuted}
        autoCapitalize="none"
        keyboardType="url"
      />

      <TouchableOpacity style={styles.secondaryBtn} onPress={handleTestConnection}>
        <Text style={styles.secondaryBtnText}>🔌 Test Connection</Text>
      </TouchableOpacity>

      <Text style={styles.sectionHeader}>Cloud Integration</Text>
      <Text style={styles.label}>Cloud Telemetry Endpoint</Text>
      <TextInput
        style={styles.input}
        value={cloudEndpoint}
        onChangeText={setCloudEndpoint}
        placeholder="https://your-endpoint.example.com/telemetry"
        placeholderTextColor={COLORS.textMuted}
        autoCapitalize="none"
        keyboardType="url"
      />

      <Text style={styles.sectionHeader}>App Preferences</Text>
      <View style={styles.toggle}>
        <View>
          <Text style={styles.toggleLabel}>Live WebSocket Updates</Text>
          <Text style={styles.toggleDesc}>Stream real-time data from orchestrator</Text>
        </View>
        <Switch
          value={liveUpdates}
          onValueChange={setLiveUpdates}
          trackColor={{ false: COLORS.border, true: COLORS.yellow }}
          thumbColor={liveUpdates ? COLORS.green : COLORS.textMuted}
        />
      </View>

      <TouchableOpacity
        style={[styles.saveBtn, saving && styles.btnDisabled]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={styles.saveBtnText}>{saving ? 'Saving…' : '💾 Save Settings'}</Text>
      </TouchableOpacity>

      <View style={styles.about}>
        <Text style={styles.pineappleEmoji}>🍍</Text>
        <Text style={styles.aboutTitle}>PiNaCoLlAda</Text>
        <Text style={styles.aboutText}>ESP32 Multi-Agent Orchestration v1.0.0</Text>
        <Text style={styles.aboutSub}>WiFi · BLE 5 · GPS/GNSS · Cloud · AI</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  sectionHeader: {
    fontSize: 12, fontWeight: '700', color: COLORS.greenDark,
    textTransform: 'uppercase', marginTop: 20, marginBottom: 8,
  },
  label: { fontSize: 11, color: COLORS.textMuted, marginBottom: 4 },
  input: {
    backgroundColor: COLORS.surface, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    padding: 10, fontSize: 14, marginBottom: 10, color: COLORS.textPrimary,
  },
  secondaryBtn: {
    borderWidth: 1, borderColor: COLORS.green, borderRadius: 8,
    padding: 10, alignItems: 'center', marginBottom: 8,
    backgroundColor: COLORS.surface,
  },
  secondaryBtnText: { color: COLORS.green, fontWeight: '600' },
  toggle: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', backgroundColor: COLORS.surface,
    borderRadius: 8, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: COLORS.border,
  },
  toggleLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  toggleDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  saveBtn: {
    backgroundColor: COLORS.yellow, borderRadius: 10,
    padding: 14, alignItems: 'center', marginTop: 16,
  },
  btnDisabled: { opacity: 0.5 },
  saveBtnText: { color: COLORS.greenDark, fontWeight: '700', fontSize: 15 },
  about: { alignItems: 'center', marginTop: 32, paddingBottom: 24 },
  pineappleEmoji: { fontSize: 36, marginBottom: 6 },
  aboutTitle: { fontSize: 18, fontWeight: '800', color: COLORS.green, letterSpacing: 1 },
  aboutText: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  aboutSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 3 },
});
