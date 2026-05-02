/// `ZoneRepository` реализация — `GET /api/v1/zones` + in-memory cache.
///
/// Кеш — простой: первый успешный ответ запоминаем, дальше возвращаем
/// из памяти. Зоны меняются редко; форсированный refresh возможен через
/// `clearCache()`.
library;

import 'package:dio/dio.dart';

import '../../core/constants.dart';
import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../domain/models/zone.dart';
import '../../domain/repositories/zone_repository.dart';
import '../api/api_exceptions.dart';
import '../api/dto/zone_dto.dart';

class ZoneRepositoryImpl implements ZoneRepository {
  ZoneRepositoryImpl({required Dio dio}) : _dio = dio;

  final Dio _dio;
  List<Zone>? _cache;

  void clearCache() {
    _cache = null;
  }

  @override
  Future<Result<List<Zone>>> listZones() async {
    final cached = _cache;
    if (cached != null) {
      return success(cached);
    }
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '$kApiVersionPrefix/zones',
      );
      final body = response.data;
      if (body == null) {
        return failure(ServerFailure.internal(detail: 'empty_response'));
      }
      final dto = ZonesPageDto.fromJson(body);
      final zones = dto.items
          .map(
            (ZoneDto z) => Zone(
              id: z.id,
              name: z.name,
              type: z.type,
              description: z.description,
              displayColor: z.displayColor,
            ),
          )
          .toList(growable: false);
      _cache = zones;
      AppLogger.instance.i('[zones.list] fetched: count=${zones.length}');
      return success(zones);
    } on DioException catch (e) {
      AppLogger.instance.w('[zones.list] failed: ${e.response?.statusCode}');
      return failure(mapDioErrorToFailure(e));
    } catch (e) {
      return failure(UnknownFailure.from(e));
    }
  }
}
