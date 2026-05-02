/// Singleton-обёртка над `sqflite`-Database для локального кэша отпечатков.
///
/// Schema v1 — одна таблица `fingerprints` с явным `sync_status`
/// (pending=0 / synced=1 / rejected=2). Партиционирование двумя таблицами
/// (queue + history) рассмотрено и отвергнуто — лишние JOIN'ы и сложнее
/// миграции при том же объёме данных.
///
/// `databaseFactory` остаётся стандартный для Android. В тестах подменяем
/// на `databaseFactoryFfi` (`sqflite_common_ffi`) и путь `:memory:`.
library;

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import '../../core/logging.dart';

const int _kDbVersion = 1;
const String kFingerprintsTable = 'fingerprints';

const String _kCreateFingerprintsTable = '''
CREATE TABLE IF NOT EXISTS $kFingerprintsTable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    rssi_vector_json TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 1,
    device_id TEXT,
    sync_status INTEGER NOT NULL DEFAULT 0,
    server_id INTEGER,
    last_error_code TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
''';

const String _kCreateIdxSyncStatus =
    'CREATE INDEX IF NOT EXISTS idx_fp_sync_status '
    'ON $kFingerprintsTable(sync_status)';

const String _kCreateIdxCapturedAt =
    'CREATE INDEX IF NOT EXISTS idx_fp_captured_at '
    'ON $kFingerprintsTable(captured_at)';

class AppDatabase {
  AppDatabase({String? path, DatabaseFactory? factory})
      : _explicitPath = path,
        _factory = factory;

  final String? _explicitPath;
  final DatabaseFactory? _factory;

  Database? _db;

  Future<Database> get database async {
    final existing = _db;
    if (existing != null && existing.isOpen) return existing;
    final db = await _open();
    _db = db;
    return db;
  }

  Future<Database> _open() async {
    final dbPath = _explicitPath ??
        p.join((await getApplicationDocumentsDirectory()).path, 'svetlyachok.db');
    AppLogger.instance.i('[db] opening: path=$dbPath, version=$_kDbVersion');

    final factory = _factory;
    if (factory != null) {
      return factory.openDatabase(
        dbPath,
        options: OpenDatabaseOptions(
          version: _kDbVersion,
          onCreate: _onCreate,
          onUpgrade: _onUpgrade,
        ),
      );
    }

    return openDatabase(
      dbPath,
      version: _kDbVersion,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  Future<void> _onCreate(Database db, int version) async {
    AppLogger.instance.i('[db] create v$version');
    final batch = db.batch()
      ..execute(_kCreateFingerprintsTable)
      ..execute(_kCreateIdxSyncStatus)
      ..execute(_kCreateIdxCapturedAt);
    await batch.commit(noResult: true);
  }

  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    AppLogger.instance.i('[db] upgrade $oldVersion → $newVersion');
    // Будущие миграции добавляются ступенями: if (oldVersion < 2) ...
  }

  Future<void> close() async {
    final db = _db;
    if (db != null) {
      await db.close();
      _db = null;
    }
  }
}
