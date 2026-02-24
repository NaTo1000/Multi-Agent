/**
 * Multi-Agent ESP32 Orchestration App
 * Cross-platform (iOS + Android) React Native application
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import DashboardScreen from './src/screens/DashboardScreen';
import DevicesScreen from './src/screens/DevicesScreen';
import FrequencyScreen from './src/screens/FrequencyScreen';
import FirmwareScreen from './src/screens/FirmwareScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import GPSMissionScreen from './src/screens/GPSMissionScreen';
import MeshManagerScreen from './src/screens/MeshManagerScreen';

const Tab = createBottomTabNavigator();

const TAB_SCREENS = [
  { name: 'Dashboard',  component: DashboardScreen,   title: 'Dashboard',         label: '📡 Home'    },
  { name: 'Devices',    component: DevicesScreen,      title: 'ESP32 Devices',     label: '🔌 Devices' },
  { name: 'Frequency',  component: FrequencyScreen,    title: 'Frequency Control', label: '📶 RF'      },
  { name: 'Firmware',   component: FirmwareScreen,     title: 'Firmware Manager',  label: '💾 FW'      },
  { name: 'Mesh',       component: MeshManagerScreen,  title: 'Mesh Network',      label: '🕸 Mesh'    },
  { name: 'GPS',        component: GPSMissionScreen,   title: 'GPS Mission',       label: '🗺 GPS'     },
  { name: 'Settings',   component: SettingsScreen,     title: 'Settings',          label: '⚙ Config'   },
];

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            tabBarActiveTintColor: '#00d4ff',
            tabBarInactiveTintColor: '#8b949e',
            tabBarStyle: { backgroundColor: '#0d1117', borderTopColor: '#30363d' },
            headerStyle: { backgroundColor: '#0d1117' },
            headerTintColor: '#00d4ff',
            headerTitleStyle: { fontWeight: 'bold', fontFamily: 'monospace' },
          }}
        >
          {TAB_SCREENS.map((s) => (
            <Tab.Screen
              key={s.name}
              name={s.name}
              component={s.component}
              options={{ title: s.title, tabBarLabel: s.label }}
            />
          ))}
        </Tab.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
