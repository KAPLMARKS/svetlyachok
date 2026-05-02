// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'wifi_network.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

/// @nodoc
mixin _$WifiNetwork {
  String get bssid => throw _privateConstructorUsedError;
  int get rssi => throw _privateConstructorUsedError;
  String? get ssid => throw _privateConstructorUsedError;
  int? get frequency => throw _privateConstructorUsedError;
  String? get capabilities => throw _privateConstructorUsedError;

  @JsonKey(ignore: true)
  $WifiNetworkCopyWith<WifiNetwork> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $WifiNetworkCopyWith<$Res> {
  factory $WifiNetworkCopyWith(
          WifiNetwork value, $Res Function(WifiNetwork) then) =
      _$WifiNetworkCopyWithImpl<$Res, WifiNetwork>;
  @useResult
  $Res call(
      {String bssid,
      int rssi,
      String? ssid,
      int? frequency,
      String? capabilities});
}

/// @nodoc
class _$WifiNetworkCopyWithImpl<$Res, $Val extends WifiNetwork>
    implements $WifiNetworkCopyWith<$Res> {
  _$WifiNetworkCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? bssid = null,
    Object? rssi = null,
    Object? ssid = freezed,
    Object? frequency = freezed,
    Object? capabilities = freezed,
  }) {
    return _then(_value.copyWith(
      bssid: null == bssid
          ? _value.bssid
          : bssid // ignore: cast_nullable_to_non_nullable
              as String,
      rssi: null == rssi
          ? _value.rssi
          : rssi // ignore: cast_nullable_to_non_nullable
              as int,
      ssid: freezed == ssid
          ? _value.ssid
          : ssid // ignore: cast_nullable_to_non_nullable
              as String?,
      frequency: freezed == frequency
          ? _value.frequency
          : frequency // ignore: cast_nullable_to_non_nullable
              as int?,
      capabilities: freezed == capabilities
          ? _value.capabilities
          : capabilities // ignore: cast_nullable_to_non_nullable
              as String?,
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$WifiNetworkImplCopyWith<$Res>
    implements $WifiNetworkCopyWith<$Res> {
  factory _$$WifiNetworkImplCopyWith(
          _$WifiNetworkImpl value, $Res Function(_$WifiNetworkImpl) then) =
      __$$WifiNetworkImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {String bssid,
      int rssi,
      String? ssid,
      int? frequency,
      String? capabilities});
}

/// @nodoc
class __$$WifiNetworkImplCopyWithImpl<$Res>
    extends _$WifiNetworkCopyWithImpl<$Res, _$WifiNetworkImpl>
    implements _$$WifiNetworkImplCopyWith<$Res> {
  __$$WifiNetworkImplCopyWithImpl(
      _$WifiNetworkImpl _value, $Res Function(_$WifiNetworkImpl) _then)
      : super(_value, _then);

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? bssid = null,
    Object? rssi = null,
    Object? ssid = freezed,
    Object? frequency = freezed,
    Object? capabilities = freezed,
  }) {
    return _then(_$WifiNetworkImpl(
      bssid: null == bssid
          ? _value.bssid
          : bssid // ignore: cast_nullable_to_non_nullable
              as String,
      rssi: null == rssi
          ? _value.rssi
          : rssi // ignore: cast_nullable_to_non_nullable
              as int,
      ssid: freezed == ssid
          ? _value.ssid
          : ssid // ignore: cast_nullable_to_non_nullable
              as String?,
      frequency: freezed == frequency
          ? _value.frequency
          : frequency // ignore: cast_nullable_to_non_nullable
              as int?,
      capabilities: freezed == capabilities
          ? _value.capabilities
          : capabilities // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc

class _$WifiNetworkImpl implements _WifiNetwork {
  const _$WifiNetworkImpl(
      {required this.bssid,
      required this.rssi,
      this.ssid,
      this.frequency,
      this.capabilities});

  @override
  final String bssid;
  @override
  final int rssi;
  @override
  final String? ssid;
  @override
  final int? frequency;
  @override
  final String? capabilities;

  @override
  String toString() {
    return 'WifiNetwork(bssid: $bssid, rssi: $rssi, ssid: $ssid, frequency: $frequency, capabilities: $capabilities)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$WifiNetworkImpl &&
            (identical(other.bssid, bssid) || other.bssid == bssid) &&
            (identical(other.rssi, rssi) || other.rssi == rssi) &&
            (identical(other.ssid, ssid) || other.ssid == ssid) &&
            (identical(other.frequency, frequency) ||
                other.frequency == frequency) &&
            (identical(other.capabilities, capabilities) ||
                other.capabilities == capabilities));
  }

  @override
  int get hashCode =>
      Object.hash(runtimeType, bssid, rssi, ssid, frequency, capabilities);

  @JsonKey(ignore: true)
  @override
  @pragma('vm:prefer-inline')
  _$$WifiNetworkImplCopyWith<_$WifiNetworkImpl> get copyWith =>
      __$$WifiNetworkImplCopyWithImpl<_$WifiNetworkImpl>(this, _$identity);
}

abstract class _WifiNetwork implements WifiNetwork {
  const factory _WifiNetwork(
      {required final String bssid,
      required final int rssi,
      final String? ssid,
      final int? frequency,
      final String? capabilities}) = _$WifiNetworkImpl;

  @override
  String get bssid;
  @override
  int get rssi;
  @override
  String? get ssid;
  @override
  int? get frequency;
  @override
  String? get capabilities;
  @override
  @JsonKey(ignore: true)
  _$$WifiNetworkImplCopyWith<_$WifiNetworkImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
