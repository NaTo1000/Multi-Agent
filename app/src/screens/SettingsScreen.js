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
        autoCapitalize="none"
        keyboardType="url"
      />

      <Text style={styles.sectionHeader}>App Preferences</Text>
      <View style={styles.toggle}>
        <View>
          <Text style={styles.toggleLabel}>Live WebSocket Updates</Text>
          <Text style={styles.toggleDesc}>Stream real-time data from orchestrator</Text>
        </View>
        <Switch value={liveUpdates} onValueChange={setLiveUpdates} />
      </View>

      <TouchableOpacity
        style={[styles.saveBtn, saving && styles.btnDisabled]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={styles.saveBtnText}>{saving ? 'Saving…' : '💾 Save Settings'}</Text>
      </TouchableOpacity>

      <View style={styles.about}>
        <Text style={styles.aboutText}>Multi-Agent ESP32 Orchestration v1.0.0</Text>
        <Text style={styles.aboutSub}>WiFi · BLE 5 · GPS/GNSS · Cloud · AI</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  sectionHeader: {
    fontSize: 12, fontWeight: '700', color: '#555',
    textTransform: 'uppercase', marginTop: 20, marginBottom: 8,
  },
  label: { fontSize: 11, color: '#888', marginBottom: 4 },
  input: {
    backgroundColor: '#fff', borderRadius: 8,
    borderWidth: 1, borderColor: '#ddd',
    padding: 10, fontSize: 14, marginBottom: 10,
  },
  secondaryBtn: {
    borderWidth: 1, borderColor: '#0066CC', borderRadius: 8,
    padding: 10, alignItems: 'center', marginBottom: 8,
  },
  secondaryBtnText: { color: '#0066CC', fontWeight: '600' },
  toggle: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', backgroundColor: '#fff',
    borderRadius: 8, padding: 12, marginBottom: 8,
  },
  toggleLabel: { fontSize: 13, fontWeight: '600', color: '#222' },
  toggleDesc: { fontSize: 11, color: '#888', marginTop: 1 },
  saveBtn: {
    backgroundColor: '#0066CC', borderRadius: 10,
    padding: 14, alignItems: 'center', marginTop: 16,
  },
  btnDisabled: { opacity: 0.5 },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  about: { alignItems: 'center', marginTop: 32, paddingBottom: 24 },
  aboutText: { fontSize: 13, color: '#888' },
  aboutSub: { fontSize: 11, color: '#aaa', marginTop: 3 },
});
