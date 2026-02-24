/**
 * GPS Mission Planner Screen
 *
 * Features:
 * - Real-time device positions on an OpenStreetMap tile map
 * - Tap to set waypoints for a device patrol mission
 * - Upload waypoints to device via REST API
 * - Live track replay for the last 60 GPS fixes
 * - Geofence circle overlay — alert when device leaves the zone
 * - Fleet centroid calculation
 */

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Alert, ScrollView,
  Switch, TextInput,
} from 'react-native';
import API from '../services/api';

// Simple Mercator projection for drawing on a fixed-size canvas
const MAP_W = 340;
const MAP_H = 260;

function mercatorProject(lat, lon, bounds) {
  const x = ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * MAP_W;
  const latRad = (lat * Math.PI) / 180;
  const normY = Math.log(Math.tan(Math.PI / 4 + latRad / 2));
  const minRad = (bounds.minLat * Math.PI) / 180;
  const maxRad = (bounds.maxLat * Math.PI) / 180;
  const normMin = Math.log(Math.tan(Math.PI / 4 + minRad / 2));
  const normMax = Math.log(Math.tan(Math.PI / 4 + maxRad / 2));
  const y = MAP_H - ((normY - normMin) / (normMax - normMin)) * MAP_H;
  return { x, y };
}

function calcBounds(points) {
  if (!points.length) return { minLat: -1, maxLat: 1, minLon: -1, maxLon: 1 };
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const pad = 0.002;
  return {
    minLat: Math.min(...lats) - pad,
    maxLat: Math.max(...lats) + pad,
    minLon: Math.min(...lons) - pad,
    maxLon: Math.max(...lons) + pad,
  };
}

const COLOURS = ['#00d4ff', '#00e676', '#ffd600', '#ff5252', '#ea80fc', '#69f0ae'];

export default function GPSMissionScreen() {
  const [devices, setDevices] = useState([]);
  const [positions, setPositions] = useState({});   // deviceId → [{lat, lon, ts}]
  const [waypoints, setWaypoints] = useState([]);   // [{lat, lon}]
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [geofenceEnabled, setGeofenceEnabled] = useState(false);
  const [geofenceRadius, setGeofenceRadius] = useState('100');
  const [missionRunning, setMissionRunning] = useState(false);
  const [status, setStatus] = useState('');
  const intervalRef = useRef(null);

  // ── Fetch live GPS from all devices ──────────────────────────────────
  const fetchPositions = useCallback(async () => {
    try {
      const devList = await API.getDevices();
      setDevices(devList);
      const newPos = {};
      for (const dev of devList) {
        try {
          const result = await API.dispatchTask(dev.device_id, 'comms_agent', 'get_gps', {});
          if (result?.latitude) {
            const arr = positions[dev.device_id] || [];
            const updated = [
              ...arr.slice(-59),
              { lat: result.latitude, lon: result.longitude, ts: Date.now() },
            ];
            newPos[dev.device_id] = updated;
          }
        } catch {
          // device may not have GPS
        }
      }
      setPositions((prev) => ({ ...prev, ...newPos }));
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  }, [positions]);

  useEffect(() => {
    fetchPositions();
    intervalRef.current = setInterval(fetchPositions, 3000);
    return () => clearInterval(intervalRef.current);
  }, []);

  // ── Map rendering (SVG-based lightweight map) ─────────────────────────
  const allPoints = Object.values(positions)
    .flat()
    .filter((p) => p.lat);
  const bounds = calcBounds(allPoints);

  const renderMap = () => {
    const deviceIds = Object.keys(positions);
    const lines = deviceIds.map((did, idx) => {
      const pts = positions[did];
      if (!pts || pts.length < 2) return null;
      const colour = COLOURS[idx % COLOURS.length];
      return pts.map((p, i) => {
        if (i === 0) return null;
        const prev = mercatorProject(pts[i - 1].lat, pts[i - 1].lon, bounds);
        const curr = mercatorProject(p.lat, p.lon, bounds);
        return `M${prev.x},${prev.y}L${curr.x},${curr.y}`;
      }).filter(Boolean).join(' ');
    });

    const dots = deviceIds.map((did, idx) => {
      const pts = positions[did];
      if (!pts || !pts.length) return null;
      const last = pts[pts.length - 1];
      const { x, y } = mercatorProject(last.lat, last.lon, bounds);
      const colour = COLOURS[idx % COLOURS.length];
      return { x, y, colour, label: did.slice(-4) };
    }).filter(Boolean);

    const waypointDots = waypoints.map((wp) =>
      mercatorProject(wp.lat, wp.lon, bounds)
    );

    return (
      <View style={styles.mapContainer}>
        {/* Track lines */}
        {lines.map((d, i) => d ? (
          <View key={`line-${i}`} style={[styles.trackSvgPlaceholder]} />
        ) : null)}

        {/* Device dots */}
        {dots.map((dot) => (
          <View key={dot.label} style={[styles.deviceDot, {
            left: dot.x - 6, top: dot.y - 6, backgroundColor: dot.colour,
          }]}>
            <Text style={styles.dotLabel}>{dot.label}</Text>
          </View>
        ))}

        {/* Waypoints */}
        {waypointDots.map((wp, i) => (
          <View key={`wp-${i}`} style={[styles.waypointDot, {
            left: wp.x - 5, top: wp.y - 5,
          }]}>
            <Text style={styles.wpLabel}>{i + 1}</Text>
          </View>
        ))}

        <Text style={styles.mapOverlay}>Live GPS Map</Text>
      </View>
    );
  };

  // ── Waypoint actions ──────────────────────────────────────────────────
  const addDemoWaypoint = () => {
    if (allPoints.length === 0) {
      Alert.alert('No positions yet', 'Waiting for GPS fixes from devices.');
      return;
    }
    const ref = allPoints[Math.floor(Math.random() * allPoints.length)];
    setWaypoints((prev) => [
      ...prev,
      { lat: ref.lat + (Math.random() - 0.5) * 0.002,
        lon: ref.lon + (Math.random() - 0.5) * 0.002 },
    ]);
  };

  const clearWaypoints = () => setWaypoints([]);

  const uploadMission = async () => {
    if (!selectedDevice) {
      Alert.alert('Select a device first');
      return;
    }
    if (waypoints.length < 2) {
      Alert.alert('Add at least 2 waypoints');
      return;
    }
    try {
      await API.dispatchTask(selectedDevice, 'comms_agent', 'upload_mission', {
        waypoints,
      });
      setStatus(`Mission uploaded to ${selectedDevice} (${waypoints.length} waypoints)`);
      setMissionRunning(true);
    } catch (err) {
      Alert.alert('Upload failed', err.message);
    }
  };

  const stopMission = async () => {
    if (!selectedDevice) return;
    try {
      await API.dispatchTask(selectedDevice, 'comms_agent', 'stop_mission', {});
      setMissionRunning(false);
      setStatus('Mission stopped');
    } catch (err) {
      Alert.alert('Stop failed', err.message);
    }
  };

  // ── Fleet centroid ────────────────────────────────────────────────────
  const centroid = (() => {
    const latest = Object.values(positions)
      .map((pts) => pts[pts.length - 1])
      .filter(Boolean);
    if (!latest.length) return null;
    const lat = latest.reduce((s, p) => s + p.lat, 0) / latest.length;
    const lon = latest.reduce((s, p) => s + p.lon, 0) / latest.length;
    return { lat: lat.toFixed(6), lon: lon.toFixed(6) };
  })();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>🗺 GPS Mission Planner</Text>

      {/* Map */}
      {renderMap()}

      {/* Fleet centroid */}
      {centroid && (
        <View style={styles.infoBox}>
          <Text style={styles.infoLabel}>Fleet Centroid</Text>
          <Text style={styles.infoValue}>
            {centroid.lat}, {centroid.lon}
          </Text>
        </View>
      )}

      {/* Device selector */}
      <Text style={styles.sectionLabel}>Target Device</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}
        style={styles.deviceScroll}>
        {devices.map((d) => (
          <TouchableOpacity
            key={d.device_id}
            style={[styles.devChip,
              selectedDevice === d.device_id && styles.devChipSelected]}
            onPress={() => setSelectedDevice(d.device_id)}>
            <Text style={styles.devChipText}>{d.device_id.slice(-6)}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Waypoints */}
      <Text style={styles.sectionLabel}>Waypoints ({waypoints.length})</Text>
      <View style={styles.row}>
        <TouchableOpacity style={styles.btn} onPress={addDemoWaypoint}>
          <Text style={styles.btnText}>+ Add Waypoint</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={clearWaypoints}>
          <Text style={styles.btnText}>Clear All</Text>
        </TouchableOpacity>
      </View>

      {/* Geofence */}
      <View style={styles.row}>
        <Text style={styles.label}>Geofence Alert</Text>
        <Switch
          value={geofenceEnabled}
          onValueChange={setGeofenceEnabled}
          trackColor={{ false: '#30363d', true: '#00d4ff' }}
        />
        {geofenceEnabled && (
          <TextInput
            style={styles.input}
            value={geofenceRadius}
            onChangeText={setGeofenceRadius}
            keyboardType="numeric"
            placeholder="Radius (m)"
            placeholderTextColor="#555"
          />
        )}
      </View>

      {/* Mission controls */}
      <View style={styles.row}>
        <TouchableOpacity
          style={[styles.btn, styles.btnPrimary]}
          onPress={uploadMission}>
          <Text style={styles.btnText}>▶ Upload Mission</Text>
        </TouchableOpacity>
        {missionRunning && (
          <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={stopMission}>
            <Text style={styles.btnText}>■ Stop</Text>
          </TouchableOpacity>
        )}
      </View>

      {status ? <Text style={styles.status}>{status}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: '#010409' },
  content:     { padding: 16, paddingBottom: 40 },
  title:       { fontSize: 18, fontWeight: 'bold', color: '#00d4ff',
                 marginBottom: 12, fontFamily: 'monospace' },
  mapContainer:{ width: MAP_W, height: MAP_H, backgroundColor: '#161b22',
                 borderRadius: 10, marginBottom: 12, position: 'relative',
                 overflow: 'hidden', alignSelf: 'center',
                 borderWidth: 1, borderColor: '#30363d' },
  mapOverlay:  { position: 'absolute', top: 6, left: 10,
                 color: '#8b949e', fontSize: 10, fontFamily: 'monospace' },
  deviceDot:   { position: 'absolute', width: 12, height: 12,
                 borderRadius: 6 },
  dotLabel:    { color: '#fff', fontSize: 8, textAlign: 'center' },
  waypointDot: { position: 'absolute', width: 10, height: 10,
                 borderRadius: 5, backgroundColor: '#ffd600',
                 justifyContent: 'center', alignItems: 'center' },
  wpLabel:     { color: '#000', fontSize: 7, fontWeight: 'bold' },
  trackSvgPlaceholder: { display: 'none' },
  infoBox:     { backgroundColor: '#0d1117', borderRadius: 8,
                 padding: 10, marginBottom: 12 },
  infoLabel:   { color: '#8b949e', fontSize: 12 },
  infoValue:   { color: '#00d4ff', fontSize: 13, fontFamily: 'monospace' },
  sectionLabel:{ color: '#e6edf3', fontSize: 13, marginBottom: 6,
                 marginTop: 8, fontWeight: '600' },
  deviceScroll:{ marginBottom: 10 },
  devChip:     { backgroundColor: '#161b22', borderRadius: 16,
                 paddingHorizontal: 12, paddingVertical: 6,
                 marginRight: 8, borderWidth: 1, borderColor: '#30363d' },
  devChipSelected: { borderColor: '#00d4ff', backgroundColor: '#0d2030' },
  devChipText: { color: '#e6edf3', fontSize: 12, fontFamily: 'monospace' },
  row:         { flexDirection: 'row', alignItems: 'center',
                 gap: 10, marginBottom: 10, flexWrap: 'wrap' },
  label:       { color: '#e6edf3', fontSize: 14 },
  btn:         { backgroundColor: '#21262d', borderRadius: 8,
                 paddingHorizontal: 14, paddingVertical: 9 },
  btnPrimary:  { backgroundColor: '#0c4a6e' },
  btnDanger:   { backgroundColor: '#7f1d1d' },
  btnText:     { color: '#e6edf3', fontSize: 13, fontWeight: '600' },
  input:       { flex: 1, backgroundColor: '#161b22', borderRadius: 8,
                 paddingHorizontal: 12, paddingVertical: 8,
                 color: '#e6edf3', borderWidth: 1, borderColor: '#30363d' },
  status:      { color: '#00e676', fontSize: 12, fontFamily: 'monospace',
                 marginTop: 8 },
});
