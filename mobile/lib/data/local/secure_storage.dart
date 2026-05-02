/// Обёртка над `flutter_secure_storage` для refresh-токена.
///
/// Refresh имеет TTL 7 дней — длинный, кража = угроза до недели.
/// На Android используется `EncryptedSharedPreferences` + Keystore.
/// Никогда не хранить в plain SharedPreferences.
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorage {
  SecureStorage([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(
                encryptedSharedPreferences: true,
              ),
            );

  final FlutterSecureStorage _storage;

  static const String _kRefreshToken = 'refresh_token';

  Future<void> saveRefreshToken(String token) async {
    await _storage.write(key: _kRefreshToken, value: token);
  }

  Future<String?> getRefreshToken() async {
    return _storage.read(key: _kRefreshToken);
  }

  Future<void> clear() async {
    await _storage.delete(key: _kRefreshToken);
  }
}
