import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/data/wifi/bssid_normalizer.dart';

void main() {
  group('normalizeBssid', () {
    test('canonical form passes through', () {
      expect(normalizeBssid('AA:BB:CC:DD:EE:FF'), 'AA:BB:CC:DD:EE:FF');
    });

    test('lowercase + colons → uppercase + colons', () {
      expect(normalizeBssid('aa:bb:cc:dd:ee:ff'), 'AA:BB:CC:DD:EE:FF');
    });

    test('uppercase + dashes → uppercase + colons', () {
      expect(normalizeBssid('AA-BB-CC-DD-EE-FF'), 'AA:BB:CC:DD:EE:FF');
    });

    test('no separators (12 hex) → canonical', () {
      expect(normalizeBssid('aabbccddeeff'), 'AA:BB:CC:DD:EE:FF');
    });

    test('mixed separators and case', () {
      expect(normalizeBssid('Aa-Bb:Cc-Dd:Ee-Ff'), 'AA:BB:CC:DD:EE:FF');
    });

    test('empty string throws', () {
      expect(() => normalizeBssid(''), throwsFormatException);
    });

    test('too short throws', () {
      expect(() => normalizeBssid('AA:BB:CC'), throwsFormatException);
    });

    test('non-hex chars throws', () {
      expect(() => normalizeBssid('GG:HH:II:JJ:KK:LL'), throwsFormatException);
    });

    test('extra chars throws', () {
      expect(() => normalizeBssid('AA:BB:CC:DD:EE:FF:00'), throwsFormatException);
    });
  });
}
