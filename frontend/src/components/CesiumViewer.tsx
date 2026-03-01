import { Viewer, CameraFlyTo } from "resium";
import { Cartesian3, Ion } from "cesium";
import DroneTracker from "./DroneTracker";
import RouteRenderer from "./RouteRenderer";
import WeatherOverlay from "./WeatherOverlay";
import LandingZoneRenderer from "./LandingZoneRenderer";
import AirspaceLayer from "./AirspaceLayer";

Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN ?? "";

const SEOUL_CENTER = Cartesian3.fromDegrees(126.978, 37.5665, 15000);

function CesiumViewer() {
  return (
    <Viewer
      full
      timeline={false}
      animation={false}
      homeButton={false}
      baseLayerPicker={false}
      navigationHelpButton={false}
      geocoder={false}
      sceneModePicker={false}
    >
      <CameraFlyTo destination={SEOUL_CENTER} duration={0} />
      <AirspaceLayer />
      <DroneTracker />
      <RouteRenderer />
      <WeatherOverlay />
      <LandingZoneRenderer />
    </Viewer>
  );
}

export default CesiumViewer;
