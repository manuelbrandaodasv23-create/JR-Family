class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'JR_API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  static const mapTileUrl = String.fromEnvironment(
    'JR_MAP_TILE_URL',
    defaultValue: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  );

  static const mapAttribution = String.fromEnvironment(
    'JR_MAP_ATTRIBUTION',
    defaultValue: '© OpenStreetMap contributors',
  );
}
