// ==============================================================================
// Mobile App Configuration for Flutter / Dart
// ==============================================================================
// Copy this file directly into your Flutter project under lib/config.dart
// ==============================================================================
// NOTE FOR DEVELOPERS:
// You only need to set [apiBaseUrl]. The app automatically constructs all other
// URLs, including the health check: "$apiBaseUrl/health".
// ==============================================================================

import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

class AppConfig {
  /// Base API URL of your backend.
  /// You ONLY need to configure this single URL.
  /// For Local development:
  /// - Android Emulator: "http://10.0.2.2:8000"
  /// - iOS Simulator: "http://localhost:8000"
  /// - Physical device on local WiFi: "http://192.168.x.x:8000"
  /// For Render Production:
  /// - "https://your-service-name.onrender.com"
  static const String apiBaseUrl = "https://your-service-name.onrender.com";

  /// Real-time WebSocket URL automatically derived from apiBaseUrl.
  /// ws:// for http and wss:// for https.
  static String get webSocketUrl {
    final uri = Uri.parse(apiBaseUrl);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    final port = uri.hasPort ? ':${uri.port}' : '';
    return "$scheme://${uri.host}$port/ws";
  }

  /// Health check endpoint automatically derived: API_BASE_URL + "/health"
  static String get healthEndpoint => "$apiBaseUrl/health";

  /// WebRTC PeerConnection default configuration.
  static const Map<String, dynamic> defaultRtcConfiguration = {
    'iceServers': [
      {'urls': 'stun:stun.l.google.com:19302'},
      {'urls': 'stun:stun1.l.google.com:19302'},
    ],
    'sdpSemantics': 'unified-plan',
  };

  /// Application REST endpoints (automatically derived from apiBaseUrl)
  static String get loginEndpoint => "$apiBaseUrl/api/auth/login";
  static String get registerEndpoint => "$apiBaseUrl/api/auth/register";
  static String get meEndpoint => "$apiBaseUrl/api/auth/me";
  static String get chatsEndpoint => "$apiBaseUrl/api/chats";
  static String get searchUsersEndpoint => "$apiBaseUrl/api/users/search";
  static String get uploadFileEndpoint => "$apiBaseUrl/api/files/upload";
  static String get rtcConfigEndpoint => "$apiBaseUrl/api/calls/config";
  static String get registerDeviceEndpoint => "$apiBaseUrl/api/devices/register";
}

/// Helper service for Render Cold Start & Server Status in Flutter
class ServerLifecycleService {
  /// Calls GET /health with a smart retry strategy for Render cold-starts.
  ///
  /// Flow:
  /// 1. Attempt immediately
  /// 2. If asleep/timeout, callback shows "Please wait... Starting server..."
  /// 3. Retries after 2s, 4s, 6s (capped up to maxDuration)
  /// 4. If fails after maxDuration, returns false so UI shows:
  ///    "Unable to connect to server. Please try again." with [ Retry ] button.
  static Future<bool> waitForServerOnline({
    Duration maxDuration = const Duration(seconds: 45),
    Function(String message)? onStatusUpdate,
  }) async {
    final stopwatch = Stopwatch()..start();
    const retryDelays = [0, 2, 4, 6, 6];
    int attempt = 0;

    while (stopwatch.elapsed < maxDuration) {
      final delaySeconds = attempt < retryDelays.length ? retryDelays[attempt] : 6;
      if (delaySeconds > 0) {
        await Future.delayed(Duration(seconds: delaySeconds));
      }

      attempt++;
      if (attempt > 1) {
        onStatusUpdate?.call("Starting server... Please wait...");
      } else {
        onStatusUpdate?.call("Connecting to server...");
      }

      try {
        final response = await http
            .get(Uri.parse(AppConfig.healthEndpoint))
            .timeout(const Duration(seconds: 10));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          if (data['status'] == 'ok') {
            onStatusUpdate?.call("Connected!");
            return true;
          }
        }
      } catch (_) {
        // Network timeout / connection refused while Render container boots
      }
    }

    return false;
  }

  /// Handles incoming WebSocket events, filtering the owner-only "server:online" alert.
  static void handleWebSocketEvent(
    Map<String, dynamic> eventJson, {
    required Function(String bannerText) onShowOwnerNotification,
  }) {
    final event = eventJson['event'];
    if (event == 'server:online') {
      final data = eventJson['data'] ?? {};
      final message = data['message'] ?? '🟢 Server is online';
      onShowOwnerNotification(message);
    }
  }
}
