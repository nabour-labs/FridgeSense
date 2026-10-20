import {WebView} from '@amazon-devices/webview';
import * as React from 'react';
import {useState} from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import {
  useHideSplashScreenCallback,
  usePreventHideSplashScreen,
} from '@amazon-devices/react-native-kepler';
import type {WebViewErrorEvent} from '@amazon-devices/webview/dist/types/WebViewTypes';
import config from '../site.config.json';
import {tvUrl} from './site';

const SOURCE = {uri: tvUrl(config.siteUrl)};

/**
 * The FridgeSense kitchen dashboard on Fire TV: the site's #tv page in a full-screen WebView.
 * Back reaches the page as a system key (it doesn't handle it, so the app closes). The app holds
 * no passcode: someone signs in once on the TV and the session stays in the WebView's storage.
 */
export const App = () => {
  usePreventHideSplashScreen();
  const hideSplashScreen = useHideSplashScreenCallback();
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <View style={styles.failed}>
        <Text style={styles.title}>Can't reach FridgeSense</Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Try again"
          hasTVPreferredFocus
          onPress={() => setFailed(false)}
          style={styles.button}>
          <Text style={styles.buttonText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <WebView
        style={styles.webview}
        source={SOURCE}
        allowSystemKeyEvents
        domStorageEnabled
        hasTVPreferredFocus
        javaScriptEnabled
        onLoad={() => hideSplashScreen()}
        onError={({nativeEvent: {code, description}}: WebViewErrorEvent) => {
          console.error(`[onError]: (${code}) ${description}`);
          hideSplashScreen();
          setFailed(true);
        }}
      />
    </View>
  );
};

// A flex container is needed for focus to reach the WebView.
const styles = StyleSheet.create({
  container: {flex: 1},
  webview: {backgroundColor: '#020617'},
  failed: {flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#020617'},
  title: {color: '#f1f5f9', fontSize: 48, fontWeight: '700', marginBottom: 40},
  button: {backgroundColor: '#2dd4bf', borderRadius: 999, paddingHorizontal: 48, paddingVertical: 20},
  buttonText: {color: '#020617', fontSize: 32, fontWeight: '700'},
});
