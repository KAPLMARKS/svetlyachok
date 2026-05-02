/// Доменная модель Wi-Fi сети из одного скана.
///
/// `bssid` уже нормализован (`AA:BB:CC:DD:EE:FF`). `rssi` clamp'нут
/// в [-100, 0] dBm. `ssid` опционален (системный API может вернуть `<unknown ssid>`).
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'wifi_network.freezed.dart';

@freezed
class WifiNetwork with _$WifiNetwork {
  const factory WifiNetwork({
    required String bssid,
    required int rssi,
    String? ssid,
    int? frequency,
    String? capabilities,
  }) = _WifiNetwork;
}
