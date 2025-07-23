import 'package:flutter/material.dart';
import 'screens/login_htmlstyle.dart';
import 'screens/register_htmlstyle.dart';
import 'screens/dashboard_htmlstyle.dart';
import 'screens/view_assets_htmlstyle.dart';
import 'screens/add_asset_htmlstyle.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hospital Inventory System',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(primarySwatch: Colors.blue),
      initialRoute: '/',
      routes: {
        '/': (context) => const LoginHtmlStyle(),
        '/dashboard': (context) => const DashboardHtmlStyle(),
        '/register_htmlstyle': (context) => const RegisterHtmlStyle(),
        '/login_htmlstyle': (context) => const LoginHtmlStyle(),
        '/view_assets': (context) => const ViewAssetsHtmlStyle(),
        '/add_asset': (context) => const AddAssetHtmlStyle(),
      },
    );
  }
}
