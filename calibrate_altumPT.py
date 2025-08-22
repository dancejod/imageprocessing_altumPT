import matplotlib.pyplot as plt
import micasense.metadata as metadata
import sys
import glob
import micasense.capture as capture
import numpy as np
import subprocess
import micasense.utils as msutils
import tifffile
from timeit import default_timer as timer
from datetime import timedelta
from pathlib import Path
from tqdm import tqdm

###PROCESSING BLUE TO NIR BANDS ONLY, i do not particularly care about the rest rn
###Place everything including panel images to one folder, include all images
#TODO: make more robust for additional bands

def run(*args):
    def compute_reflectance_factor_with_panel(panel_cap, reference_reflectances):
        try:
            for i, val in enumerate(reference_reflectances):
                radiancePanelImage = panel_cap.images[i].radiance()
                ur, ul, ll, lr = panel_cap.images[i].panel_region
                radiancePanelRegion = radiancePanelImage[lr[1]:ul[1], ul[0]:lr[0]]
                radianceReflectanceFactor = val / radiancePanelRegion.mean()
            return radianceReflectanceFactor
        except Exception:
            print("No calibration panel detected")
            return None

    root_path = Path(args[0])

    outpath = root_path / "calibrated"
    outpath.mkdir(exist_ok=True)

    #our panel reflectances
    ALTUMPT_REFLECTANCE_BY_BAND = [0.508, 0.509, 0.509, 0.509, 0.506]

    imageNames = list(root_path.glob("IMG_*.tif"))
    #skip panchro and thermal
    imageNames = [x.as_posix() for x in imageNames if not (
        x.stem.endswith("6") or x.stem.endswith("_7")
    )]

    #before flight panel images
    panelNamesBefore = imageNames[:5]
    
    #panelNamesBefore = [x.as_posix() for x in panelNamesBefore]
    panelCapBefore = capture.Capture.from_filelist(panelNamesBefore)

    #after flight panel images
    panelNamesAfter = imageNames[-5:]
    #panelNamesAfter = [x.as_posix() for x in panelNamesAfter]
    panelCapAfter = capture.Capture.from_filelist(panelNamesAfter)

    

    flightImageNames = imageNames[5:-5]
    out_paths = []

    time_start = timer()
    print(f"{'[Calibration]':<15} Started calibrating flight images")

    for i in tqdm(range(0, len(flightImageNames), 5), desc="Processing flight images"):
        imgs = flightImageNames[i:i+5]
        imgsCap = capture.Capture.from_filelist(imgs)
        radianceReflectanceFactorBefore = compute_reflectance_factor_with_panel(panelCapBefore, ALTUMPT_REFLECTANCE_BY_BAND)
        radianceReflectanceFactorAfter = compute_reflectance_factor_with_panel(panelCapAfter, ALTUMPT_REFLECTANCE_BY_BAND)
        
        if radianceReflectanceFactorBefore is None and radianceReflectanceFactorAfter is None:
            pass
        elif radianceReflectanceFactorBefore is not None and radianceReflectanceFactorAfter is not None:
            interpolate = True
        else:
            interpolate = False
            radianceReflectanceFactor = radianceReflectanceFactorBefore if radianceReflectanceFactorBefore is not None else radianceReflectanceFactorAfter

        for b, image in enumerate(imgs):
            if interpolate:
                #linearly interpolate reflectance factor for current band and flight img
                radianceReflectanceFactor = np.interp(imgsCap.utc_time().timestamp(),
                                                    [
                                                        panelCapBefore.utc_time().timestamp(),
                                                        panelCapAfter.utc_time().timestamp(),
                                                    ], [
                                                        radianceReflectanceFactorBefore, radianceReflectanceFactorAfter
                                                    ])
                
            flightImage = plt.imread(image)
            flightRadianceImage, _, _, _ = msutils.raw_image_to_radiance(metadata.Metadata(panelNamesBefore[b]), flightImage)
            flightReflectanceImage = flightRadianceImage * radianceReflectanceFactor
            
            in_path = Path(imgs[b])
            out = outpath / in_path.name
            
            tifffile.imwrite(out, flightReflectanceImage.astype("float32"))

            out_paths.append(out)

    time_end = timer()
    print(f"{'[Calibration]':<15} Calibrated in: {timedelta(seconds=time_end - time_start)}")

    exiftime_start = timer()
    print(f"{'[EXIF]':<15} Updating metadata of calibrated images...")
    subprocess.run(["exiftool", "-config", "altumconfigexif.cfg", "-tagsfromfile", f"{root_path}/%f.tif", outpath, "-xmp:all","-gps:all", "-overwrite_original"])
    exiftime_end = timer()
    print(f"{'[EXIF]':<15} Image metadata updated in: {timedelta(seconds=exiftime_end - exiftime_start)}")

    print(f"{'[Done]':<15} Successfully calibrated {len(flightImageNames)} flight images")

if __name__ == "__main__":
    run(sys.argv[1])