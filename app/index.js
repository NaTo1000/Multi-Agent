/**
 * Multi-Agent ESP32 Orchestration App — entry point
 *
 * Registers the root React Native application component so Metro and the
 * native runtime can bootstrap the app on both iOS and Android.
 */

import { AppRegistry } from 'react-native';
import App from './App';
import { name as appName } from './package.json';

AppRegistry.registerComponent(appName, () => App);
