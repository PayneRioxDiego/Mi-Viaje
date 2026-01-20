import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { ExternalLink, MapPin, Globe } from 'lucide-react';

// Icono personalizado (Igual que antes)
const customIcon = new L.Icon({
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

interface MapProps { items: any[]; }

function ChangeView({ center }: { center: [number, number] }) {
    const map = useMap();
    map.setView(center, 4);
    return null;
}

const MapComponent: React.FC<MapProps> = ({ items }) => {
    
    const validMarkers = items.filter(item => {
        const lat = Number(item.lat);
        const lng = Number(item.lng);
        return !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;
    });

    const defaultCenter: [number, number] = validMarkers.length > 0 
        ? [Number(validMarkers[0].lat), Number(validMarkers[0].lng)] 
        : [20, 0]; 

    return (
        <div className="w-full h-full relative z-0 bg-slate-100">
             {validMarkers.length === 0 && (
                <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-white/90 px-6 py-3 rounded-full shadow-xl text-sm font-bold text-slate-500 flex items-center gap-2 border border-slate-200 backdrop-blur-sm">
                    <Globe className="h-4 w-4 text-indigo-500" />
                    <span>Sin ubicaciones GPS válidas</span>
                </div>
             )}

             <MapContainer center={defaultCenter} zoom={validMarkers.length > 0 ? 4 : 2} scrollWheelZoom={true} style={{ height: '100%', width: '100%' }}>
                
                {/* --- AQUÍ ESTÁ EL CAMBIO DE VELOCIDAD --- */}
                <TileLayer 
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                />
                {/* ---------------------------------------- */}
                
                {validMarkers.length > 0 && <ChangeView center={[Number(validMarkers[0].lat), Number(validMarkers[0].lng)]} />}

                {validMarkers.map((item) => (
                    <Marker key={`marker-${item.id}`} position={[Number(item.lat), Number(item.lng)]} icon={customIcon}>
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
                                {item.mapsLink && (
                                    <a href={item.mapsLink} target="_blank" rel="noreferrer" className="text-xs bg-slate-900 text-white py-2 rounded-md text-center flex items-center justify-center gap-1 hover:bg-black transition-colors font-bold shadow-md">
                                        Abrir GPS <ExternalLink className="h-3 w-3" />
                                    </a>
                                )}
                            </div>
                        </Popup>
                    </Marker>
                ))}
            </MapContainer>
        </div>
    );
};
export default MapComponent;
