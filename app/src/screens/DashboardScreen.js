/**
 * Dashboard Screen — real-time orchestrator overview
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
  ActivityIndicator,
} from 'react-native';
import API from '../services/api';
import COLORS from '../theme';

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
        <ActivityIndicator size="large" color={COLORS.yellow} />
        <Text style={styles.loadingText}>Connecting to orchestrator…</Text>
      </View>
    );
  }

  const onlineDevices = devices.filter((d) => d.status === 'online').length;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={COLORS.yellow}
          colors={[COLORS.yellow]}
        />
      }
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
      <View style={[styles.dot, { backgroundColor: COLORS.yellow }]} />
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
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.background },
  loadingText: { marginTop: 12, color: COLORS.textMuted },
  statusBar: { padding: 8, alignItems: 'center' },
  connected: { backgroundColor: '#D6F0E0' },
  disconnected: { backgroundColor: '#FFF8DC' },
  statusText: { fontWeight: '600', fontSize: 13, color: COLORS.textPrimary },
  statsRow: { flexDirection: 'row', padding: 12, gap: 8 },
  card: {
    flex: 1, backgroundColor: COLORS.surface, borderRadius: 10,
    padding: 12, alignItems: 'center', elevation: 2,
    borderWidth: 1, borderColor: COLORS.border,
  },
  cardValue: { fontSize: 28, fontWeight: 'bold', color: COLORS.green },
  cardTitle: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  cardSub: { fontSize: 11, color: COLORS.textMuted },
  sectionHeader: {
    fontSize: 14, fontWeight: '700', color: COLORS.greenDark,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4,
    textTransform: 'uppercase', letterSpacing: 0.5,
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: COLORS.surface, paddingHorizontal: 16,
    paddingVertical: 12, marginBottom: 1,
  },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.textMuted, marginRight: 12 },
  dotGreen: { backgroundColor: COLORS.success },
  dotRed: { backgroundColor: COLORS.danger },
  rowTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  rowSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 1 },
  rowRight: { marginLeft: 'auto', fontSize: 12, color: COLORS.textSecondary },
  empty: { textAlign: 'center', color: COLORS.textMuted, padding: 24 },
});
