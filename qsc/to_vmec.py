"""
This module contains the routines to output a
near-axis boundary to a VMEC input file
"""
from .Frenet_to_cylindrical import Frenet_to_cylindrical
import numpy as np
from .util import mu0
from datetime import datetime

def to_Fourier(R_2D, Z_2D, nfp, ntheta, mpol, ntor, lasym):
    """
    This function takes two 2D arrays (R_2D and Z_2D), which contain
    the values of the radius R and vertical coordinate Z in cylindrical
    coordinates of a given surface and Fourier transform it, outputing
    the resulting cos(theta) and sin(theta) Fourier coefficients

    Args:
        R_2D: 2D array of the radial coordinate R(theta,phi) of a given surface
        Z_2D: 2D array of the vertical coordinate Z(theta,phi) of a given surface
        nfp: number of field periods of the surface
        ntheta: poloidal resolution
        mpol: resolution in poloidal Fourier space
        ntor: resolution in toroidal Fourier space
        lasym: False if stellarator-symmetric, True if not
    """
    nphi_conversion = np.array(R_2D).shape[1]
    theta = np.linspace(0,2*np.pi,ntheta,endpoint=False)
    phi_conversion = np.linspace(0,2*np.pi/nfp,nphi_conversion,endpoint=False)
    RBC = np.zeros((int(2*ntor+1),int(mpol+1)))
    RBS = np.zeros((int(2*ntor+1),int(mpol+1)))
    ZBC = np.zeros((int(2*ntor+1),int(mpol+1)))
    ZBS = np.zeros((int(2*ntor+1),int(mpol+1)))
    factor = 2 / (ntheta * nphi_conversion)
    for j_phi in range(nphi_conversion):
        for j_theta in range(ntheta):
            for m in range(mpol+1):
                nmin = -ntor
                if m==0: nmin = 1
                for n in range(nmin, ntor+1):
                    angle = m * theta[j_theta] - n * nfp * phi_conversion[j_phi]
                    sinangle = np.sin(angle)
                    cosangle = np.cos(angle)
                    factor2 = factor
                    # The next 2 lines ensure inverse Fourier transform(Fourier transform) = identity
                    if np.mod(ntheta,2) == 0 and m  == (ntheta/2): factor2 = factor2 / 2
                    if np.mod(nphi_conversion,2) == 0 and abs(n) == (nphi_conversion/2): factor2 = factor2 / 2
                    RBC[n+ntor,m] = RBC[n+ntor,m] + R_2D[j_theta, j_phi] * cosangle * factor2
                    RBS[n+ntor,m] = RBS[n+ntor,m] + R_2D[j_theta, j_phi] * sinangle * factor2
                    ZBC[n+ntor,m] = ZBC[n+ntor,m] + Z_2D[j_theta, j_phi] * cosangle * factor2
                    ZBS[n+ntor,m] = ZBS[n+ntor,m] + Z_2D[j_theta, j_phi] * sinangle * factor2
    RBC[ntor,0] = np.sum(R_2D) / (ntheta * nphi_conversion)
    ZBC[ntor,0] = np.sum(Z_2D) / (ntheta * nphi_conversion)

    if not lasym:
        RBS = 0
        ZBC = 0

    return RBC, RBS, ZBC, ZBS

def to_vmec(self, filename, r=0.1, params=dict(), ntheta=20, ntorMax=14):
    """
    Outputs the near-axis configuration calculated with pyQSC to
    a text file that is able to be read by VMEC.

    Args:
        filename: name of the text file to be created
        r:  near-axis radius r of the desired boundary surface
        params: a Python dict() instance containing one/several of the following parameters: mpol,
        delt, nstep, tcon0, ns_array, ftol_array, niter_array
        ntheta: resolution in the poloidal angle theta for the Frenet_to_cylindrical and VMEC calculations
        ntorMax: maximum number of NTOR in the resulting VMEC input file
    """
    if "mpol" not in params.keys():
        mpol1d = 100 # maximum number of mode numbers VMEC can handle
        mpol = int(np.floor(min(ntheta / 2, mpol1d)))
    else:
        mpol = int(params["mpol"])
    if "ntor" not in params.keys():
        # We should be able to resolve (N_phi-1)/2 modes (note integer division!), but in case N_phi is very large, don't attempt more than the vmec arrays can handle.
        ntord = 100 # maximum number of mode numbers VMEC can handle
        ntor = int(min(self.nphi / 2 + 1, ntord))
    else:
        ntor = int(params["ntor"])
    if "delt" not in params.keys():
        params["delt"] = 0.9
    if "nstep" not in params.keys():
        params["nstep"] = 200
    if "tcon0" not in params.keys():
        params["tcon0"] = 2.0
    if "ns_array" not in params.keys():
        params["ns_array"] = [16,49,101]
    if "ftol_array" not in params.keys():
        params["ftol_array"] = [1e-13,1e-12,1e-11]
    if "niter_array" not in params.keys():
        params["niter_array"] = [1000,1000,1500]

    phiedge = np.pi * r * r * self.spsi * self.Bbar

    # Set pressure Profile
    temp = - self.p2 * r * r
    am = [temp,-temp]
    pmass_type='power_series'
    pres_scale=1

    # Set current profile:
    ncurr = 1
    pcurr_type = 'power_series'
    ac = [1]
    curtor = 2 * np.pi / mu0 * self.I2 * r * r

    # Get surface shape at fixed off-axis toroidal angle phi
    R_2D, Z_2D, phi0_2D = self.Frenet_to_cylindrical(r, ntheta)
    
    # Fourier transform the result.
    # This is not a rate-limiting step, so for clarity of code, we don't bother with an FFT.
    RBC, RBS, ZBC, ZBS = to_Fourier(R_2D, Z_2D, self.nfp, ntheta, mpol, ntor, self.lasym)

    # Write to VMEC file
    file_object = open(filename,"w+")
    file_object.write("! This &INDATA namelist was generated by pyQSC: github.com/landreman/pyQSC\n")
    file_object.write("! Date: "+datetime.now().strftime("%B %d, %Y")+", Time: "+datetime.now().strftime("%H:%M:%S")+" UTC"+datetime.now().astimezone().strftime("%z")+"\n")
    file_object.write('! Near-axis parameters:  radius r = '+str(r)+', etabar = '+str(self.etabar)+'\n')
    file_object.write('! nphi = '+str(self.nphi)+', order = '+self.order+', sigma0 = '+str(self.sigma0)+', I2 = '+str(self.I2)+', B0 = '+str(self.B0)+'\n')
    file_object.write('! Resolution parameters: ntheta = '+str(ntheta)+', mpol = '+str(mpol)+', ntor = '+str(ntor)+'\n')
    file_object.write('!----- Runtime Parameters -----\n')
    file_object.write('&INDATA\n')
    file_object.write('  DELT = '+str(params["delt"])+'\n')
    file_object.write('  NSTEP = '+str(params["nstep"])+'\n')
    file_object.write('  TCON0 = '+str(params["tcon0"])+'\n')
    file_object.write('  NS_ARRAY = '+str(params["ns_array"])[1:-1]+'\n')
    file_object.write('  FTOL_ARRAY = '+str(params["ftol_array"])[1:-1]+'\n')
    file_object.write('  NITER_ARRAY = '+str(params["niter_array"])[1:-1]+'\n')
    file_object.write('!----- Grid Parameters -----\n')
    file_object.write('  LASYM = '+str(self.lasym)+'\n')
    file_object.write('  NFP = '+str(self.nfp)+'\n')
    file_object.write('  MPOL = '+str(mpol)+'\n')
    file_object.write('  NTOR = '+str(min(ntor,ntorMax))+'\n')
    file_object.write('  PHIEDGE = '+str(phiedge)+'\n')
    file_object.write('!----- Pressure Parameters -----\n')
    file_object.write('  PRES_SCALE = '+str(pres_scale)+'\n')
    file_object.write("  PMASS_TYPE = '"+pmass_type+"'\n")
    file_object.write('  AM = '+str(am)[1:-1]+'\n')
    file_object.write('!----- Current/Iota Parameters -----\n')
    file_object.write('  CURTOR = '+str(curtor)+'\n')
    file_object.write('  NCURR = '+str(ncurr)+'\n')
    file_object.write("  PCURR_TYPE = '"+pcurr_type+"'\n")
    file_object.write('  AC = '+str(ac)[1:-1]+'\n')
    file_object.write('!----- Axis Parameters -----\n')
    # To convert sin(...) modes to vmec, we introduce a minus sign. This is because in vmec,
    # R and Z ~ sin(m theta - n phi), which for m=0 is sin(-n phi) = -sin(n phi).
    file_object.write('  RAXIS_CC = '+str(self.rc)[1:-1]+'\n')
    if self.lasym:
        file_object.write('  RAXIS_CS = '+str(-self.rs)[1:-1]+'\n')
        file_object.write('  ZAXIS_CC = '+str(self.zc)[1:-1]+'\n')
    file_object.write('  ZAXIS_CS = '+str(-self.zs)[1:-1]+'\n')
    file_object.write('!----- Boundary Parameters -----\n')
    for m in range(mpol+1):
        for n in range(-ntor,ntor+1):
            if RBC[n+ntor,m]!=0 or ZBS[n+ntor,m]!=0:
                file_object.write(    '  RBC('+f"{n:03d}"+','+f"{m:03d}"+') = '+f"{RBC[n+ntor,m]:+.16e}"+',    ZBS('+f"{n:03d}"+','+f"{m:03d}"+') = '+f"{ZBS[n+ntor,m]:+.16e}"+'\n')
                if self.lasym:
                    file_object.write('  RBS('+f"{n:03d}"+','+f"{m:03d}"+') = '+f"{RBS[n+ntor,m]:+.16e}"+',    ZBC('+f"{n:03d}"+','+f"{m:03d}"+') = '+f"{ZBC[n+ntor,m]:+.16e}"+'\n')
    file_object.write('/\n')
    file_object.close()

    self.RBC = RBC.transpose()
    self.ZBS = ZBS.transpose()
    if self.lasym:
        self.RBS = RBS.transpose()
        self.ZBC = ZBC.transpose()
    else:
        self.RBS = RBS
        self.ZBC = ZBC