/**
 * Firmware Manager Screen
 * Build and flash ESP32 firmware on-the-fly
 */

import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, Switch,
} from 'react-native';
import API from '../services/api';

const FEATURE_OPTIONS = ['wifi', 'ble', 'gps'];
const TEMPLATE_OPTIONS = ['base'];

export default function FirmwareScreen() {
  const [template, setTemplate] = useState('base');
  const [features, setFeatures] = useState({ wifi: true, ble: false, gps: false });
  const [version, setVersion] = useState('');
  const [building, setBuilding] = useState(false);
  const [lastBuild, setLastBuild] = useState(null);

  const toggleFeature = (f) => setFeatures((prev) => ({ ...prev, [f]: !prev[f] }));

  const handleBuild = async () => {
    const activeFeatures = Object.entries(features)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (activeFeatures.length === 0) {
      Alert.alert('Validation', 'Select at least one feature');
      return;
    }
    setBuilding(true);
    try {
      const result = await API.buildFirmware(
        template,
        activeFeatures,
        version || null,
      );
      setLastBuild(result?.result || result);
      Alert.alert('Build', `Build ${result?.result?.build_id || 'dispatched'} complete`);
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setBuilding(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.sectionHeader}>Build Configuration</Text>

      {/* Template */}
      <Text style={styles.label}>Template</Text>
      <View style={styles.chips}>
        {TEMPLATE_OPTIONS.map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.chip, template === t && styles.chipActive]}
            onPress={() => setTemplate(t)}
          >
            <Text style={[styles.chipText, template === t && styles.chipTextActive]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Features */}
      <Text style={styles.label}>Features</Text>
      {FEATURE_OPTIONS.map((f) => (
        <View key={f} style={styles.featureRow}>
          <View>
            <Text style={styles.featureName}>{f.toUpperCase()}</Text>
            <Text style={styles.featureDesc}>{featureDesc(f)}</Text>
          </View>
          <Switch value={features[f]} onValueChange={() => toggleFeature(f)} />
        </View>
      ))}

      {/* Version */}
      <Text style={styles.label}>Version (optional)</Text>
      <TextInput
        style={styles.input}
        value={version}
        onChangeText={setVersion}
        placeholder="e.g. 2.0.1 (auto-generated if blank)"
      />

      {/* Build button */}
      <TouchableOpacity
        style={[styles.buildBtn, building && styles.btnDisabled]}
        onPress={handleBuild}
        disabled={building}
      >
        <Text style={styles.buildBtnText}>
          {building ? '⚙️ Building…' : '🔨 Build Firmware'}
        </Text>
      </TouchableOpacity>

      {/* Last build result */}
      {lastBuild && (
        <View style={styles.resultCard}>
          <Text style={styles.sectionHeader}>Last Build</Text>
          <MetaRow label="Build ID" value={lastBuild.build_id} />
          <MetaRow label="Version" value={lastBuild.version} />
          <MetaRow label="Template" value={lastBuild.template} />
          <MetaRow label="Features" value={(lastBuild.features || []).join(', ')} />
          <MetaRow label="Compiled" value={lastBuild.compiled ? '✅ Yes' : '⚠️ Placeholder'} />
          <MetaRow label="Timestamp" value={lastBuild.timestamp?.slice(0, 19)} />
        </View>
      )}
    </ScrollView>
  );
}

function MetaRow({ label, value }) {
  return (
    <View style={{ flexDirection: 'row', marginBottom: 6 }}>
      <Text style={{ fontSize: 12, color: '#888', width: 80 }}>{label}</Text>
      <Text style={{ fontSize: 12, color: '#222', flex: 1 }}>{value}</Text>
    </View>
  );
}

function featureDesc(f) {
  return {
    wifi: 'WiFi STA + HTTP API server + OTA updates',
    ble: 'BLE 5 advertising + GATT command server',
    gps: 'GPS/GNSS NMEA parsing + location API',
  }[f] || '';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  sectionHeader: { fontSize: 14, fontWeight: '700', color: '#333', marginBottom: 10, textTransform: 'uppercase' },
  label: { fontSize: 11, fontWeight: '700', color: '#888', marginBottom: 6, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: '#0066CC' },
  chipActive: { backgroundColor: '#0066CC' },
  chipText: { fontSize: 12, color: '#0066CC' },
  chipTextActive: { color: '#fff' },
  featureRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', backgroundColor: '#fff',
    borderRadius: 8, padding: 12, marginBottom: 8,
  },
  featureName: { fontSize: 13, fontWeight: '700', color: '#222' },
  featureDesc: { fontSize: 11, color: '#888', marginTop: 2, maxWidth: 260 },
  input: {
    backgroundColor: '#fff', borderRadius: 8,
    borderWidth: 1, borderColor: '#ddd',
    padding: 10, fontSize: 14, marginBottom: 16,
  },
  buildBtn: {
    backgroundColor: '#0066CC', borderRadius: 10,
    padding: 14, alignItems: 'center', marginBottom: 16,
  },
  btnDisabled: { opacity: 0.5 },
  buildBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  resultCard: { backgroundColor: '#fff', borderRadius: 10, padding: 14 },
});
