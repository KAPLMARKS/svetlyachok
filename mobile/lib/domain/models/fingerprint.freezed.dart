// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'fingerprint.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

/// @nodoc
mixin _$Fingerprint {
  DateTime get capturedAt => throw _privateConstructorUsedError;
  Map<String, int> get rssiVector => throw _privateConstructorUsedError;
  int get sampleCount => throw _privateConstructorUsedError;
  String? get deviceId => throw _privateConstructorUsedError;
  int? get localId => throw _privateConstructorUsedError;
  int? get serverId => throw _privateConstructorUsedError;
  SyncStatus get syncStatus => throw _privateConstructorUsedError;

  @JsonKey(ignore: true)
  $FingerprintCopyWith<Fingerprint> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $FingerprintCopyWith<$Res> {
  factory $FingerprintCopyWith(
          Fingerprint value, $Res Function(Fingerprint) then) =
      _$FingerprintCopyWithImpl<$Res, Fingerprint>;
  @useResult
  $Res call(
      {DateTime capturedAt,
      Map<String, int> rssiVector,
      int sampleCount,
      String? deviceId,
      int? localId,
      int? serverId,
      SyncStatus syncStatus});
}

/// @nodoc
class _$FingerprintCopyWithImpl<$Res, $Val extends Fingerprint>
    implements $FingerprintCopyWith<$Res> {
  _$FingerprintCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? capturedAt = null,
    Object? rssiVector = null,
    Object? sampleCount = null,
    Object? deviceId = freezed,
    Object? localId = freezed,
    Object? serverId = freezed,
    Object? syncStatus = null,
  }) {
    return _then(_value.copyWith(
      capturedAt: null == capturedAt
          ? _value.capturedAt
          : capturedAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      rssiVector: null == rssiVector
          ? _value.rssiVector
          : rssiVector // ignore: cast_nullable_to_non_nullable
              as Map<String, int>,
      sampleCount: null == sampleCount
          ? _value.sampleCount
          : sampleCount // ignore: cast_nullable_to_non_nullable
              as int,
      deviceId: freezed == deviceId
          ? _value.deviceId
          : deviceId // ignore: cast_nullable_to_non_nullable
              as String?,
      localId: freezed == localId
          ? _value.localId
          : localId // ignore: cast_nullable_to_non_nullable
              as int?,
      serverId: freezed == serverId
          ? _value.serverId
          : serverId // ignore: cast_nullable_to_non_nullable
              as int?,
      syncStatus: null == syncStatus
          ? _value.syncStatus
          : syncStatus // ignore: cast_nullable_to_non_nullable
              as SyncStatus,
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$FingerprintImplCopyWith<$Res>
    implements $FingerprintCopyWith<$Res> {
  factory _$$FingerprintImplCopyWith(
          _$FingerprintImpl value, $Res Function(_$FingerprintImpl) then) =
      __$$FingerprintImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {DateTime capturedAt,
      Map<String, int> rssiVector,
      int sampleCount,
      String? deviceId,
      int? localId,
      int? serverId,
      SyncStatus syncStatus});
}

/// @nodoc
class __$$FingerprintImplCopyWithImpl<$Res>
    extends _$FingerprintCopyWithImpl<$Res, _$FingerprintImpl>
    implements _$$FingerprintImplCopyWith<$Res> {
  __$$FingerprintImplCopyWithImpl(
      _$FingerprintImpl _value, $Res Function(_$FingerprintImpl) _then)
      : super(_value, _then);

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? capturedAt = null,
    Object? rssiVector = null,
    Object? sampleCount = null,
    Object? deviceId = freezed,
    Object? localId = freezed,
    Object? serverId = freezed,
    Object? syncStatus = null,
  }) {
    return _then(_$FingerprintImpl(
      capturedAt: null == capturedAt
          ? _value.capturedAt
          : capturedAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      rssiVector: null == rssiVector
          ? _value._rssiVector
          : rssiVector // ignore: cast_nullable_to_non_nullable
              as Map<String, int>,
      sampleCount: null == sampleCount
          ? _value.sampleCount
          : sampleCount // ignore: cast_nullable_to_non_nullable
              as int,
      deviceId: freezed == deviceId
          ? _value.deviceId
          : deviceId // ignore: cast_nullable_to_non_nullable
              as String?,
      localId: freezed == localId
          ? _value.localId
          : localId // ignore: cast_nullable_to_non_nullable
              as int?,
      serverId: freezed == serverId
          ? _value.serverId
          : serverId // ignore: cast_nullable_to_non_nullable
              as int?,
      syncStatus: null == syncStatus
          ? _value.syncStatus
          : syncStatus // ignore: cast_nullable_to_non_nullable
              as SyncStatus,
    ));
  }
}

/// @nodoc

class _$FingerprintImpl implements _Fingerprint {
  const _$FingerprintImpl(
      {required this.capturedAt,
      required final Map<String, int> rssiVector,
      this.sampleCount = 1,
      this.deviceId,
      this.localId,
      this.serverId,
      this.syncStatus = SyncStatus.pending})
      : _rssiVector = rssiVector;

  @override
  final DateTime capturedAt;
  final Map<String, int> _rssiVector;
  @override
  Map<String, int> get rssiVector {
    if (_rssiVector is EqualUnmodifiableMapView) return _rssiVector;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableMapView(_rssiVector);
  }

  @override
  @JsonKey()
  final int sampleCount;
  @override
  final String? deviceId;
  @override
  final int? localId;
  @override
  final int? serverId;
  @override
  @JsonKey()
  final SyncStatus syncStatus;

  @override
  String toString() {
    return 'Fingerprint(capturedAt: $capturedAt, rssiVector: $rssiVector, sampleCount: $sampleCount, deviceId: $deviceId, localId: $localId, serverId: $serverId, syncStatus: $syncStatus)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$FingerprintImpl &&
            (identical(other.capturedAt, capturedAt) ||
                other.capturedAt == capturedAt) &&
            const DeepCollectionEquality()
                .equals(other._rssiVector, _rssiVector) &&
            (identical(other.sampleCount, sampleCount) ||
                other.sampleCount == sampleCount) &&
            (identical(other.deviceId, deviceId) ||
                other.deviceId == deviceId) &&
            (identical(other.localId, localId) || other.localId == localId) &&
            (identical(other.serverId, serverId) ||
                other.serverId == serverId) &&
            (identical(other.syncStatus, syncStatus) ||
                other.syncStatus == syncStatus));
  }

  @override
  int get hashCode => Object.hash(
      runtimeType,
      capturedAt,
      const DeepCollectionEquality().hash(_rssiVector),
      sampleCount,
      deviceId,
      localId,
      serverId,
      syncStatus);

  @JsonKey(ignore: true)
  @override
  @pragma('vm:prefer-inline')
  _$$FingerprintImplCopyWith<_$FingerprintImpl> get copyWith =>
      __$$FingerprintImplCopyWithImpl<_$FingerprintImpl>(this, _$identity);
}

abstract class _Fingerprint implements Fingerprint {
  const factory _Fingerprint(
      {required final DateTime capturedAt,
      required final Map<String, int> rssiVector,
      final int sampleCount,
      final String? deviceId,
      final int? localId,
      final int? serverId,
      final SyncStatus syncStatus}) = _$FingerprintImpl;

  @override
  DateTime get capturedAt;
  @override
  Map<String, int> get rssiVector;
  @override
  int get sampleCount;
  @override
  String? get deviceId;
  @override
  int? get localId;
  @override
  int? get serverId;
  @override
  SyncStatus get syncStatus;
  @override
  @JsonKey(ignore: true)
  _$$FingerprintImplCopyWith<_$FingerprintImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
