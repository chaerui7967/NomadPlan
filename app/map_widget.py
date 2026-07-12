"""지도를 그리는 위젯.

내부적으로 QWebEngineView 위에 Leaflet(무료) 또는 네이버 지도 JS를 올려서 표시한다.
Python 쪽에서는 provider 종류에 상관없이 동일한 메서드
(add_marker, clear_markers, draw_route, clear_route, fit_to_markers)만 호출하면 되고,
실제 지도 JS 구현 차이는 이 클래스 안에서만 처리한다.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

_LEAFLET_HEAD = """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
"""

_LEAFLET_SCRIPT = """
var map = L.map('map').setView([37.5665, 126.9780], 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

var markers = [];
var routeLine = null;

function addMarker(lat, lng, label) {
    var m = L.marker([lat, lng]).addTo(map);
    if (label) { m.bindPopup(label); }
    markers.push(m);
    return markers.length - 1;
}

function clearMarkers() {
    markers.forEach(function(m){ map.removeLayer(m); });
    markers = [];
}

function drawRoute(coordsJsonStr) {
    var coords = JSON.parse(coordsJsonStr);
    if (routeLine) { map.removeLayer(routeLine); }
    if (coords.length === 0) return;
    routeLine = L.polyline(coords, {color: '#2d6cdf', weight: 5, opacity: 0.85}).addTo(map);
}

function clearRoute() {
    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
}

function fitToMarkers() {
    if (markers.length === 0) return;
    var group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.25));
}

function setCenter(lat, lng, zoom) {
    map.setView([lat, lng], zoom || map.getZoom());
}
"""

_NAVER_HEAD_TMPL = """
<script type="text/javascript" src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={client_id}"></script>
"""

_NAVER_SCRIPT = """
var map = new naver.maps.Map('map', {
  center: new naver.maps.LatLng(37.5665, 126.9780),
  zoom: 11
});
var markers = [];
var routeLine = null;

function addMarker(lat, lng, label) {
  var marker = new naver.maps.Marker({
    position: new naver.maps.LatLng(lat, lng),
    map: map,
    title: label || ''
  });
  markers.push(marker);
  return markers.length - 1;
}

function clearMarkers() {
  markers.forEach(function(m){ m.setMap(null); });
  markers = [];
}

function drawRoute(coordsJsonStr) {
  var coords = JSON.parse(coordsJsonStr);
  if (routeLine) { routeLine.setMap(null); routeLine = null; }
  if (coords.length === 0) return;
  var path = coords.map(function(c){ return new naver.maps.LatLng(c[0], c[1]); });
  routeLine = new naver.maps.Polyline({
    map: map,
    path: path,
    strokeColor: '#2d6cdf',
    strokeWeight: 5,
    strokeOpacity: 0.85
  });
}

function clearRoute() {
  if (routeLine) { routeLine.setMap(null); routeLine = null; }
}

function fitToMarkers() {
  if (markers.length === 0) return;
  var bounds = new naver.maps.LatLngBounds(markers[0].getPosition(), markers[0].getPosition());
  markers.forEach(function(m){ bounds.extend(m.getPosition()); });
  map.fitBounds(bounds);
}

function setCenter(lat, lng, zoom) {
  map.setCenter(new naver.maps.LatLng(lat, lng));
  if (zoom) map.setZoom(zoom);
}
"""

_GOOGLE_HEAD_TMPL = """
<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?key={api_key}"></script>
"""

_GOOGLE_SCRIPT = """
var map = new google.maps.Map(document.getElementById('map'), {
  center: {lat: 37.5665, lng: 126.9780},
  zoom: 11
});
var markers = [];
var routeLine = null;

function addMarker(lat, lng, label) {
  var marker = new google.maps.Marker({
    position: {lat: lat, lng: lng},
    map: map,
    title: label || ''
  });
  markers.push(marker);
  return markers.length - 1;
}

function clearMarkers() {
  markers.forEach(function(m){ m.setMap(null); });
  markers = [];
}

function drawRoute(coordsJsonStr) {
  var coords = JSON.parse(coordsJsonStr);
  if (routeLine) { routeLine.setMap(null); routeLine = null; }
  if (coords.length === 0) return;
  var path = coords.map(function(c){ return {lat: c[0], lng: c[1]}; });
  routeLine = new google.maps.Polyline({
    map: map,
    path: path,
    strokeColor: '#2d6cdf',
    strokeWeight: 5,
    strokeOpacity: 0.85
  });
}

function clearRoute() {
  if (routeLine) { routeLine.setMap(null); routeLine = null; }
}

function fitToMarkers() {
  if (markers.length === 0) return;
  var bounds = new google.maps.LatLngBounds();
  markers.forEach(function(m){ bounds.extend(m.getPosition()); });
  map.fitBounds(bounds);
}

function setCenter(lat, lng, zoom) {
  map.setCenter({lat: lat, lng: lng});
  if (zoom) map.setZoom(zoom);
}
"""

_PAGE_TMPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
</style>
{head_extra}
</head>
<body>
<div id="map"></div>
<script>
{map_script}
</script>
</body>
</html>
"""


class MapWidget(QWebEngineView):
    """지도 표시 및 마커/경로 그리기를 담당하는 위젯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config: Dict[str, Any] = {"type": "leaflet"}
        self.setMinimumHeight(280)
        self.set_provider_config(self._config)

    def set_provider_config(self, config: Dict[str, Any]) -> None:
        """provider.js_map_config()의 반환값을 받아 지도 종류를 전환/재로딩."""
        self._config = config
        provider_type = config.get("type")
        if provider_type == "naver":
            head_extra = _NAVER_HEAD_TMPL.format(client_id=config.get("client_id", ""))
            script = _NAVER_SCRIPT
        elif provider_type == "google":
            head_extra = _GOOGLE_HEAD_TMPL.format(api_key=config.get("api_key", ""))
            script = _GOOGLE_SCRIPT
        else:
            head_extra = _LEAFLET_HEAD
            script = _LEAFLET_SCRIPT

        html = _PAGE_TMPL.format(head_extra=head_extra, map_script=script)
        # baseUrl을 https로 지정해 일부 브라우저 보안 정책(mixed content 등) 문제를 줄임
        self.setHtml(html, QUrl("https://localhost/"))

    # ---- Python -> JS 호출 헬퍼 ----

    def _run_js(self, code: str) -> None:
        self.page().runJavaScript(code)

    def clear_all(self) -> None:
        self._run_js("clearMarkers(); clearRoute();")

    def add_marker(self, lat: float, lng: float, label: str = "") -> None:
        safe_label = json.dumps(label or "")
        self._run_js(f"addMarker({lat}, {lng}, {safe_label});")

    def draw_route(self, path: List[Tuple[float, float]]) -> None:
        coords_json = json.dumps([[p[0], p[1]] for p in path])
        self._run_js(f"drawRoute({json.dumps(coords_json)});")

    def clear_route(self) -> None:
        self._run_js("clearRoute();")

    def fit_to_markers(self) -> None:
        self._run_js("fitToMarkers();")

    def set_center(self, lat: float, lng: float, zoom: Optional[int] = None) -> None:
        self._run_js(f"setCenter({lat}, {lng}, {zoom or 'null'});")

    def render_stops(self, stops) -> None:
        """Stop 리스트 전체를 지도에 다시 그림 (마커 + 누적 경로)."""
        self.clear_all()
        for stop in stops:
            label = stop.name or stop.address

            if stop.note:
                label += f" · {stop.note}"

            self.add_marker(stop.lat, stop.lng, label)

        full_path: List[Tuple[float, float]] = []
        for stop in stops:
            if stop.path:
                full_path.extend(stop.path)
        if full_path:
            self.draw_route(full_path)
        if stops:
            self.fit_to_markers()
