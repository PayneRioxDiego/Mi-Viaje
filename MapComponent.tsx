import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { ExternalLink, MapPin, Globe } from 'lucide-react';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon, shadowUrl: iconShadow,
    iconSize: [25, 41], iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

interface MapProps { items: any[]; }

function ChangeView({ center }: { center: [number, number] }) {
    const map = useMap();
    map.setView(center, 13); // Zoom más cercano
    return null;
}

const MapComponent: React.FC<MapProps> = ({ items }) => {
    
    // FILTRO DE ORO: Solo mostramos items que tengan coordenadas válidas
    const validMarkers = items.filter(item => {
        const lat = parseFloat(item.lat);
        const lng = parseFloat(item.lng);
        return !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;
    });

    // Si no hay marcadores válidos, mostramos el mundo entero
    const defaultCenter: [number, number] = validMarkers.length > 0 
        ? [validMarkers[0].lat, validMarkers[0].lng]
        : [20, 0]; 

    return (
        <div className="w-full h-full relative z-0 bg-slate-100">
             <MapContainer center={defaultCenter} zoom={validMarkers.length > 0 ? 4 : 2} scrollWheelZoom={true} style={{ height: '100%', width: '100%' }}>
                <TileLayer attribution='© OSM' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                
                {/* Centra el mapa en el primer resultado válido */}
                {validMarkers.length > 0 && <ChangeView center={[validMarkers[0].lat, validMarkers[0].lng]} />}

                {validMarkers.map((item) => (
                    <Marker key={`marker-${item.id}`} position={[item.lat, item.lng]}>
                        <Popup className="custom-popup">
                            <div className="flex flex-col min-w-[160px]">
                                {item.photoUrl && (
                                    <div className="w-full h-24 mb-2 overflow-hidden rounded-lg relative bg-slate-100">
                                        <img src={item.photoUrl} alt={item.placeName} className="w-full h-full object-cover" />
                                    </div>
                                )}
                                <h3 className="font-black text-slate-800 text-sm leading-tight mb-1">{item.placeName}</h3>
                                <div className="flex items-center text-[10px] text-slate-500 mb-2 uppercase tracking-wide">
                                    <MapPin className="h-3 w-3 mr-1 text-indigo-500" />
                                    {item.category}
                                </div>
                                <a href={item.mapsLink} target="_blank" rel="noreferrer" className="text-xs bg-slate-900 text-white py-2 rounded-md text-center flex items-center justify-center gap-1 hover:bg-black transition-colors font-bold shadow-md">
                                    Abrir GPS <ExternalLink className="h-3 w-3" />
                                </a>
                            </div>
                        </Popup>
                    </Marker>
                ))}
            </MapContainer>
        </div>
    );
};
export default MapComponent;
