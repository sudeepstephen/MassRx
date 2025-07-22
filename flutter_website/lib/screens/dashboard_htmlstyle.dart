import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class DashboardHtmlStyle extends StatefulWidget {
  const DashboardHtmlStyle({super.key});

  @override
  State<DashboardHtmlStyle> createState() => _DashboardHtmlStyleState();
}

class _DashboardHtmlStyleState extends State<DashboardHtmlStyle> {
  String? role;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    loadUserRole();
  }

  Future<void> loadUserRole() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');

    if (token == null) {
      Navigator.pushReplacementNamed(context, '/');
      return;
    }

    final res = await http.get(
      Uri.parse('https://yourdomain.com/api/me'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (res.statusCode == 200) {
      final user = jsonDecode(res.body);
      setState(() {
        role = user['role'];
        loading = false;
      });
    } else {
      setState(() => loading = false);
      Navigator.pushReplacementNamed(context, '/');
    }
  }

  Widget buildNavButton(String label, String route, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: ElevatedButton(
        onPressed: () => Navigator.pushNamed(context, route),
        style: ElevatedButton.styleFrom(
          backgroundColor: color ?? const Color(0xff007bff),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
        child: Text(
          label,
          style: const TextStyle(color: Colors.white, fontSize: 16),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xfff4f4f4),
      body: Center(
        child: Container(
          padding: const EdgeInsets.all(24),
          constraints: const BoxConstraints(maxWidth: 800),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'Dashboard',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              if (loading)
                const CircularProgressIndicator()
              else if (role == 'purchaser')
                buildNavButton('Purchase Order History', '/purchase_history')
              else
                Wrap(
                  alignment: WrapAlignment.center,
                  children: [
                    buildNavButton('Assets', '/view_assets'),
                    buildNavButton('Create Work Order', '/create_work_order'),
                    buildNavButton('View Work Orders', '/view_work_orders'),
                    buildNavButton(
                      'Purchase Order History',
                      '/purchase_history',
                    ),
                    if (role == 'director')
                      buildNavButton(
                        'Facility Access Management',
                        '/facility_access',
                      ),
                  ],
                ),
              const SizedBox(height: 30),
              buildNavButton('Logout', '/', color: const Color(0xffdc3545)),
            ],
          ),
        ),
      ),
    );
  }
}
