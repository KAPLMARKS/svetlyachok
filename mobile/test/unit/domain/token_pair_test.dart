import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/domain/models/token_pair.dart';

void main() {
  group('TokenPair.isAccessExpired', () {
    test('returns false for fresh access (issued just now, ttl=1800)', () {
      final pair = TokenPair(
        accessToken: 'a',
        refreshToken: 'r',
        expiresIn: 1800,
        issuedAt: DateTime.now().toUtc(),
      );
      expect(pair.isAccessExpired, isFalse);
    });

    test('returns true when issuedAt is older than expiresIn', () {
      final pair = TokenPair(
        accessToken: 'a',
        refreshToken: 'r',
        expiresIn: 1800,
        issuedAt: DateTime.now().toUtc().subtract(const Duration(hours: 2)),
      );
      expect(pair.isAccessExpired, isTrue);
    });

    test('returns true within refresh buffer (last 30 sec)', () {
      // expiresIn=60, issuedAt=now -45s → through 30-sec buffer уже expired
      final pair = TokenPair(
        accessToken: 'a',
        refreshToken: 'r',
        expiresIn: 60,
        issuedAt: DateTime.now().toUtc().subtract(const Duration(seconds: 45)),
      );
      expect(pair.isAccessExpired, isTrue);
    });
  });
}
