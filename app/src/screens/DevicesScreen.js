/**
 * Devices Screen — list, add, ping, and manage ESP32 modules
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  Modal, TextInput, Alert, ActivityIndicator,
} from 'react-native';
import API from '../services/api';

export default function DevicesScreen() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addModal, setAddModal] = useState(false);
  const [form, setForm] = useState({ device_id: '', name: '', ip_address: '' });

  const load = async () => {
    try {
      setDevices(await API.listDevices());
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!form.device_id || !form.name) {
      Alert.alert('Validation', 'Device ID and Name are required');
      return;
    }
    try {
      await API.registerDevice({ ...form, capabilities: ['wifi', 'ble'] });
      setAddModal(false);
      setForm({ device_id: '', name: '', ip_address: '' });
      load();
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  };

  const handlePing = async (deviceId) => {
    try {
      const r = await API.pingDevice(deviceId);
      Alert.alert('Ping', r.online ? '✅ Device is online' : '❌ Device is offline');
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  };

  const renderDevice = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.name}>{item.name}</Text>
          <Text style={styles.sub}>{item.ip_address || 'No IP'}</Text>
        </View>
        <View style={[styles.badge, item.status === 'online' ? styles.badgeGreen : styles.badgeRed]}>
          <Text style={styles.badgeText}>{item.status}</Text>
        </View>
      </View>

      <View style={styles.meta}>
        <MetaItem label="FW" value={item.firmware_version} />
        <MetaItem label="RSSI" value={item.rssi != null ? `${item.rssi} dBm` : '—'} />
        <MetaItem
          label="Caps"
          value={(item.capabilities || []).join(', ') || '—'}
        />
      </View>

      <View style={styles.actions}>
        <ActionBtn label="Ping" onPress={() => handlePing(item.device_id)} />
        <ActionBtn label="Optimise" onPress={async () => {
          try {
            await API.optimiseDevice(item.device_id);
            Alert.alert('AI', 'Optimisation dispatched');
          } catch (e) {
            Alert.alert('Error', e.message);
          }
        }} />
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={devices}
        keyExtractor={(d) => d.device_id}
        renderItem={renderDevice}
        refreshing={loading}
        onRefresh={load}
        ListEmptyComponent={
          <Text style={styles.empty}>No devices registered.{'\n'}Tap + to add one.</Text>
        }
        contentContainerStyle={{ padding: 12 }}
      />

      <TouchableOpacity style={styles.fab} onPress={() => setAddModal(true)}>
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>

      {/* Add device modal */}
      <Modal visible={addModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Add ESP32 Device</Text>
            <TextInput style={styles.input} placeholder="Device ID (e.g. esp32-001)"
              value={form.device_id}
              onChangeText={(v) => setForm({ ...form, device_id: v })} />
            <TextInput style={styles.input} placeholder="Name"
              value={form.name}
              onChangeText={(v) => setForm({ ...form, name: v })} />
            <TextInput style={styles.input} placeholder="IP Address (optional)"
              value={form.ip_address}
              onChangeText={(v) => setForm({ ...form, ip_address: v })} />
            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.btnSecondary} onPress={() => setAddModal(false)}>
                <Text>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.btnPrimary} onPress={handleAdd}>
                <Text style={styles.btnPrimaryText}>Add Device</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function MetaItem({ label, value }) {
  return (
    <View style={{ marginRight: 16 }}>
      <Text style={{ fontSize: 10, color: '#888' }}>{label}</Text>
      <Text style={{ fontSize: 12, color: '#333', fontWeight: '600' }}>{value}</Text>
    </View>
  );
}

function ActionBtn({ label, onPress }) {
  return (
    <TouchableOpacity style={styles.actionBtn} onPress={onPress}>
      <Text style={styles.actionBtnText}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  card: {
    backgroundColor: '#fff', borderRadius: 10,
    padding: 14, marginBottom: 10, elevation: 2,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 15, fontWeight: '700', color: '#222' },
  sub: { fontSize: 12, color: '#888', marginTop: 1 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  badgeGreen: { backgroundColor: '#d4edda' },
  badgeRed: { backgroundColor: '#f8d7da' },
  badgeText: { fontSize: 11, fontWeight: '600' },
  meta: { flexDirection: 'row', marginTop: 10, marginBottom: 10 },
  actions: { flexDirection: 'row', gap: 8 },
  actionBtn: {
    flex: 1, padding: 8, borderRadius: 6,
    borderWidth: 1, borderColor: '#0066CC', alignItems: 'center',
  },
  actionBtnText: { color: '#0066CC', fontSize: 12, fontWeight: '600' },
  empty: { textAlign: 'center', color: '#999', marginTop: 60, fontSize: 14 },
  fab: {
    position: 'absolute', right: 20, bottom: 20,
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: '#0066CC', alignItems: 'center', justifyContent: 'center',
    elevation: 4,
  },
  fabText: { color: '#fff', fontSize: 30, lineHeight: 34 },
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  modal: {
    backgroundColor: '#fff', borderTopLeftRadius: 16,
    borderTopRightRadius: 16, padding: 20,
  },
  modalTitle: { fontSize: 17, fontWeight: '700', marginBottom: 16 },
  input: {
    borderWidth: 1, borderColor: '#ddd', borderRadius: 8,
    padding: 10, marginBottom: 12, fontSize: 14,
  },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
  btnSecondary: {
    flex: 1, padding: 12, borderRadius: 8,
    borderWidth: 1, borderColor: '#ddd', alignItems: 'center',
  },
  btnPrimary: {
    flex: 1, padding: 12, borderRadius: 8,
    backgroundColor: '#0066CC', alignItems: 'center',
  },
  btnPrimaryText: { color: '#fff', fontWeight: '700' },
});
