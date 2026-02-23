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

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            tabBarActiveTintColor: '#0066CC',
            tabBarInactiveTintColor: '#999',
            headerStyle: { backgroundColor: '#0066CC' },
            headerTintColor: '#fff',
            headerTitleStyle: { fontWeight: 'bold' },
          }}
        >
          <Tab.Screen
            name="Dashboard"
            component={DashboardScreen}
            options={{ title: 'Dashboard', tabBarLabel: 'Dashboard' }}
          />
          <Tab.Screen
            name="Devices"
            component={DevicesScreen}
            options={{ title: 'ESP32 Devices', tabBarLabel: 'Devices' }}
          />
          <Tab.Screen
            name="Frequency"
            component={FrequencyScreen}
            options={{ title: 'Frequency Control', tabBarLabel: 'Frequency' }}
          />
          <Tab.Screen
            name="Firmware"
            component={FirmwareScreen}
            options={{ title: 'Firmware Manager', tabBarLabel: 'Firmware' }}
          />
          <Tab.Screen
            name="Settings"
            component={SettingsScreen}
            options={{ title: 'Settings', tabBarLabel: 'Settings' }}
          />
        </Tab.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
