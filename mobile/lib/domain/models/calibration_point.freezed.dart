// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'calibration_point.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

/// @nodoc
mixin _$CalibrationPoint {
  int get id => throw _privateConstructorUsedError;
  int get zoneId => throw _privateConstructorUsedError;
  DateTime get capturedAt => throw _privateConstructorUsedError;
  Map<String, int> get rssiVector => throw _privateConstructorUsedError;
  int get sampleCount => throw _privateConstructorUsedError;

  @JsonKey(ignore: true)
  $CalibrationPointCopyWith<CalibrationPoint> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $CalibrationPointCopyWith<$Res> {
  factory $CalibrationPointCopyWith(
          CalibrationPoint value, $Res Function(CalibrationPoint) then) =
      _$CalibrationPointCopyWithImpl<$Res, CalibrationPoint>;
  @useResult
  $Res call(
      {int id,
      int zoneId,
      DateTime capturedAt,
      Map<String, int> rssiVector,
      int sampleCount});
}

/// @nodoc
class _$CalibrationPointCopyWithImpl<$Res, $Val extends CalibrationPoint>
    implements $CalibrationPointCopyWith<$Res> {
  _$CalibrationPointCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? zoneId = null,
    Object? capturedAt = null,
    Object? rssiVector = null,
    Object? sampleCount = null,
  }) {
    return _then(_value.copyWith(
      id: null == id
          ? _value.id
          : id // ignore: cast_nullable_to_non_nullable
              as int,
      zoneId: null == zoneId
          ? _value.zoneId
          : zoneId // ignore: cast_nullable_to_non_nullable
              as int,
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
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$CalibrationPointImplCopyWith<$Res>
    implements $CalibrationPointCopyWith<$Res> {
  factory _$$CalibrationPointImplCopyWith(_$CalibrationPointImpl value,
          $Res Function(_$CalibrationPointImpl) then) =
      __$$CalibrationPointImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {int id,
      int zoneId,
      DateTime capturedAt,
      Map<String, int> rssiVector,
      int sampleCount});
}

/// @nodoc
class __$$CalibrationPointImplCopyWithImpl<$Res>
    extends _$CalibrationPointCopyWithImpl<$Res, _$CalibrationPointImpl>
    implements _$$CalibrationPointImplCopyWith<$Res> {
  __$$CalibrationPointImplCopyWithImpl(_$CalibrationPointImpl _value,
      $Res Function(_$CalibrationPointImpl) _then)
      : super(_value, _then);

  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? zoneId = null,
    Object? capturedAt = null,
    Object? rssiVector = null,
    Object? sampleCount = null,
  }) {
    return _then(_$CalibrationPointImpl(
      id: null == id
          ? _value.id
          : id // ignore: cast_nullable_to_non_nullable
              as int,
      zoneId: null == zoneId
          ? _value.zoneId
          : zoneId // ignore: cast_nullable_to_non_nullable
              as int,
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
    ));
  }
}

/// @nodoc

class _$CalibrationPointImpl implements _CalibrationPoint {
  const _$CalibrationPointImpl(
      {required this.id,
      required this.zoneId,
      required this.capturedAt,
      required final Map<String, int> rssiVector,
      this.sampleCount = 1})
      : _rssiVector = rssiVector;

  @override
  final int id;
  @override
  final int zoneId;
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
  String toString() {
    return 'CalibrationPoint(id: $id, zoneId: $zoneId, capturedAt: $capturedAt, rssiVector: $rssiVector, sampleCount: $sampleCount)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$CalibrationPointImpl &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.zoneId, zoneId) || other.zoneId == zoneId) &&
            (identical(other.capturedAt, capturedAt) ||
                other.capturedAt == capturedAt) &&
            const DeepCollectionEquality()
                .equals(other._rssiVector, _rssiVector) &&
            (identical(other.sampleCount, sampleCount) ||
                other.sampleCount == sampleCount));
  }

  @override
  int get hashCode => Object.hash(runtimeType, id, zoneId, capturedAt,
      const DeepCollectionEquality().hash(_rssiVector), sampleCount);

  @JsonKey(ignore: true)
  @override
  @pragma('vm:prefer-inline')
  _$$CalibrationPointImplCopyWith<_$CalibrationPointImpl> get copyWith =>
      __$$CalibrationPointImplCopyWithImpl<_$CalibrationPointImpl>(
          this, _$identity);
}

abstract class _CalibrationPoint implements CalibrationPoint {
  const factory _CalibrationPoint(
      {required final int id,
      required final int zoneId,
      required final DateTime capturedAt,
      required final Map<String, int> rssiVector,
      final int sampleCount}) = _$CalibrationPointImpl;

  @override
  int get id;
  @override
  int get zoneId;
  @override
  DateTime get capturedAt;
  @override
  Map<String, int> get rssiVector;
  @override
  int get sampleCount;
  @override
  @JsonKey(ignore: true)
  _$$CalibrationPointImplCopyWith<_$CalibrationPointImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
