import * as React from 'react';
import {act, render, screen} from '@testing-library/react-native';
import {App} from '../src/App';

jest.mock('@amazon-devices/webview', () => ({
  WebView: 'WebView',
}));

jest.mock('@amazon-devices/react-native-kepler', () => ({
  usePreventHideSplashScreen: jest.fn(),
  useHideSplashScreenCallback: jest.fn(() => jest.fn()),
  StyleSheet: {create: (styles: unknown) => styles, flatten: (style: unknown) => style},
  View: 'View',
  Text: 'Text',
  Pressable: 'Pressable',
}));

jest.mock('../site.config.json', () => ({siteUrl: 'https://d1example.cloudfront.net'}), {virtual: true});

const tryAgain = () => screen.UNSAFE_getByProps({accessibilityLabel: 'Try again'});
const webView = () => screen.UNSAFE_queryByType('WebView' as never);

// WebView settings
test('the WebView loads the TV dashboard with storage, system keys and focus', () => {
  render(<App />);
  const props = webView()!.props;
  expect(props.source).toEqual({uri: 'https://d1example.cloudfront.net/#tv'});
  expect(props.domStorageEnabled).toBe(true);
  expect(props.allowSystemKeyEvents).toBe(true);
  expect(props.hasTVPreferredFocus).toBe(true);
});

// Offline TV
test('a load error shows Can\'t reach FridgeSense with a focused Try again', () => {
  render(<App />);
  act(() => webView()!.props.onError({nativeEvent: {code: -2, url: 'x', description: 'offline'}}));
  expect(screen.getByText("Can't reach FridgeSense")).toBeTruthy();
  expect(tryAgain().props.hasTVPreferredFocus).toBe(true);
  expect(webView()).toBeNull();
});

// Try again
test('Try again shows the WebView again with the #tv source', () => {
  render(<App />);
  act(() => webView()!.props.onError({nativeEvent: {code: -2, url: 'x', description: 'offline'}}));
  act(() => tryAgain().props.onPress());
  expect(webView()!.props.source).toEqual({uri: 'https://d1example.cloudfront.net/#tv'});
  expect(screen.queryByText("Can't reach FridgeSense")).toBeNull();
});
