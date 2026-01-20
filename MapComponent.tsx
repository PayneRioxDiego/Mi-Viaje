import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { ExternalLink, MapPin, Globe } from 'lucide-react';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

interface MapProps {
    items: any[];
}

function ChangeView({ center }: { center: [number, number] }) {
    const map = useMap();
    map.setView(center, 4);
    return null;
}

const MapComponent: React.FC<MapProps> = ({ items }) => {
    
    const extractCoords = (link: string): [number, number] | null => {
        if (!link) return null;
        try {
            const parts = link.split('/0');
            if (parts.length > 1) {
                const coords = parts[1].split(',');
                const lat = parseFloat(coords[0]);
                const lng = parseFloat(coords[1]);
                if (!isNaN(lat) && !isNaN(lng)) return [lat, lng];
            }
            return null;
        } catch (e) { return null; }
    };

    const validMarkers = items
        .map(item => ({ ...item, coords: extractCoords(item.mapsLink) }))
        .filter(item => item.coords !== null);

    const defaultCenter: [number, number] = validMarkers.length > 0 
        ? validMarkers[0].coords 
        : [20, -40]; 

    return (
        <div className="w-full h-full relative z-0 bg-slate-100">
             {validMarkers.length === 0 && (
                <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-white/90 px-6 py-3 rounded-full shadow-xl text-sm font-bold text-slate-500 flex items-center gap-2 border border-slate-200 backdrop-blur-sm">
                    <Globe className="h-4 w-4 text-indigo-500" />
                    <span>Analiza videos para ver el mapa</span>
                </div>
             )}

             <MapContainer 
                center={defaultCenter} 
                zoom={validMarkers.length > 0 ? 4 : 2} 
                scrollWheelZoom={true} 
                style={{ height: '100%', width: '100%' }}
            >
                <TileLayer
                    attribution='&copy; OSM & CartoDB'
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                />
                {validMarkers.length > 0 && <ChangeView center={validMarkers[0].coords} />}
                {validMarkers.map((item) => (
                    <Marker key={`marker-${item.id}`} position={item.coords}>
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
