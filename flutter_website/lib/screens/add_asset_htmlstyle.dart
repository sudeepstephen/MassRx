import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class AddAssetHtmlStyle extends StatefulWidget {
  const AddAssetHtmlStyle({super.key});

  @override
  State<AddAssetHtmlStyle> createState() => _AddAssetHtmlStyleState();
}

class _AddAssetHtmlStyleState extends State<AddAssetHtmlStyle> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {
    'tag_number': TextEditingController(),
    'description': TextEditingController(),
    'type_desc': TextEditingController(),
    'manufacturer_desc': TextEditingController(),
    'model_num': TextEditingController(),
    'equ_model_name': TextEditingController(),
    'orig_manufacturer_desc': TextEditingController(),
    'serial_num': TextEditingController(),
    'udi_code': TextEditingController(),
    'guid': TextEditingController(),
    'equ_status_desc': TextEditingController(),
    'facility_id': TextEditingController(),
  };

  bool loading = false;
  String? token;

  Future<void> submitAsset() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => loading = true);

    final prefs = await SharedPreferences.getInstance();
    token = prefs.getString('token');

    final body = <String, String>{};
    for (var entry in _controllers.entries) {
      body[entry.key] = entry.value.text.trim();
    }

    final uri = Uri.parse('http://localhost:8888/api/assets');
    final req = http.MultipartRequest('POST', uri);
    req.headers['Authorization'] = 'Bearer $token';
    req.fields.addAll(body);

    final response = await req.send();
    setState(() => loading = false);

    if (response.statusCode == 200) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('✅ Asset submitted successfully')),
      );
      Navigator.pushReplacementNamed(context, '/view_assets');
    } else {
      final resp = await response.stream.bytesToString();
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed: $resp')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add New Asset')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              ..._controllers.entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10.0),
                  child: TextFormField(
                    controller: entry.value,
                    decoration: InputDecoration(
                      labelText: entry.key.replaceAll('_', ' ').toUpperCase(),
                      border: const OutlineInputBorder(),
                    ),
                    validator: (val) =>
                        val == null || val.isEmpty ? 'Required' : null,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              loading
                  ? const CircularProgressIndicator()
                  : ElevatedButton(
                      onPressed: submitAsset,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xff007bff),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 30,
                          vertical: 14,
                        ),
                      ),
                      child: const Text(
                        'Submit Asset',
                        style: TextStyle(color: Colors.white),
                      ),
                    ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: () =>
                    Navigator.pushReplacementNamed(context, '/view_assets'),
                child: const Text('Back to Assets'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
