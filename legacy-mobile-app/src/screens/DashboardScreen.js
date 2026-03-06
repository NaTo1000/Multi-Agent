/**
 * Dashboard Screen — real-time orchestrator overview
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  ActivityIndicator,
} from 'react-native';
import API from '../services/api';

export default function DashboardScreen() {
  const [status, setStatus] = useState(null);
  const [devices, setDevices] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [s, d, a] = await Promise.all([
        API.getStatus(),
        API.listDevices(),
        API.listAgents(),
      ]);
      setStatus(s);
      setDevices(d);
      setAgents(a);
    } catch (e) {
      console.warn('Dashboard load error:', e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // WebSocket for live updates
    API.connectWS((msg) => {
      if (msg.type === 'status') {
        setStatus(msg.orchestrator);
        setDevices(msg.devices || []);
        setWsConnected(true);
      }
    });
    return () => API.disconnectWS();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0066CC" />
        <Text style={styles.loadingText}>Connecting to orchestrator…</Text>
      </View>
    );
  }

  const onlineDevices = devices.filter((d) => d.status === 'online').length;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Connection status */}
      <View style={[styles.statusBar, wsConnected ? styles.connected : styles.disconnected]}>
        <Text style={styles.statusText}>
          {wsConnected ? '● Live' : '○ Polling'} — Orchestrator{' '}
          {status?.running ? 'Running' : 'Stopped'}
        </Text>
      </View>

      {/* Stats row */}
      <View style={styles.statsRow}>
        <StatCard title="Devices" value={devices.length} sub={`${onlineDevices} online`} />
        <StatCard title="Agents" value={agents.length} sub="registered" />
        <StatCard title="Tasks" value={status?.pending_tasks ?? 0} sub="queued" />
      </View>

      {/* Devices */}
      <SectionHeader title="ESP32 Devices" />
      {devices.length === 0 ? (
        <Text style={styles.empty}>No devices registered</Text>
      ) : (
        devices.map((d) => <DeviceRow key={d.device_id} device={d} />)
      )}

      {/* Agents */}
      <SectionHeader title="Active Agents" />
      {agents.map((a) => <AgentRow key={a.agent_id} agent={a} />)}
    </ScrollView>
  );
}

function StatCard({ title, value, sub }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardValue}>{value}</Text>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardSub}>{sub}</Text>
    </View>
  );
}

function DeviceRow({ device }) {
  const online = device.status === 'online';
  return (
    <View style={styles.row}>
      <View style={[styles.dot, online ? styles.dotGreen : styles.dotRed]} />
      <View>
        <Text style={styles.rowTitle}>{device.name}</Text>
        <Text style={styles.rowSub}>{device.ip_address || device.device_id}</Text>
      </View>
      <Text style={styles.rowRight}>{device.firmware_version}</Text>
    </View>
  );
}

function AgentRow({ agent }) {
  return (
    <View style={styles.row}>
      <View style={styles.dot} />
      <View>
        <Text style={styles.rowTitle}>{agent.agent_type}</Text>
        <Text style={styles.rowSub}>Status: {agent.status}</Text>
      </View>
      <Text style={styles.rowRight}>
        ✓ {agent.tasks_completed}
      </Text>
    </View>
  );
}

function SectionHeader({ title }) {
  return <Text style={styles.sectionHeader}>{title}</Text>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { marginTop: 12, color: '#666' },
  statusBar: { padding: 8, alignItems: 'center' },
  connected: { backgroundColor: '#d4edda' },
  disconnected: { backgroundColor: '#fff3cd' },
  statusText: { fontWeight: '600', fontSize: 13 },
  statsRow: { flexDirection: 'row', padding: 12, gap: 8 },
  card: {
    flex: 1, backgroundColor: '#fff', borderRadius: 8,
    padding: 12, alignItems: 'center', elevation: 2,
  },
  cardValue: { fontSize: 28, fontWeight: 'bold', color: '#0066CC' },
  cardTitle: { fontSize: 12, color: '#444', marginTop: 2 },
  cardSub: { fontSize: 11, color: '#888' },
  sectionHeader: {
    fontSize: 14, fontWeight: '700', color: '#333',
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4,
    textTransform: 'uppercase', letterSpacing: 0.5,
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', paddingHorizontal: 16,
    paddingVertical: 12, marginBottom: 1,
  },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#aaa', marginRight: 12 },
  dotGreen: { backgroundColor: '#28a745' },
  dotRed: { backgroundColor: '#dc3545' },
  rowTitle: { fontSize: 14, fontWeight: '600', color: '#222' },
  rowSub: { fontSize: 12, color: '#777', marginTop: 1 },
  rowRight: { marginLeft: 'auto', fontSize: 12, color: '#555' },
  empty: { textAlign: 'center', color: '#999', padding: 24 },
});
