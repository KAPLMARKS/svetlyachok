import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/domain/models/user.dart';

void main() {
  group('User.isAdmin', () {
    test('returns true when role == "admin"', () {
      const user = User(
        id: 1,
        email: 'a@b.c',
        fullName: 'Admin',
        role: 'admin',
        isActive: true,
      );
      expect(user.isAdmin, isTrue);
    });

    test('returns false for role == "employee"', () {
      const user = User(
        id: 2,
        email: 'a@b.c',
        fullName: 'Emp',
        role: 'employee',
        isActive: true,
      );
      expect(user.isAdmin, isFalse);
    });
  });
}
