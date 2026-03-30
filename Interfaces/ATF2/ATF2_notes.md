## Notes for the DR

caget DR:monitors

DR:monitors

 array(i+0)  ... BPM(k) status (1=normal, others=error)

 array(i+1)  ... BPM(k) xpos

 array(i+2)  ... BPM(k) ypos

 array(i+3)  ... BPM(k) intensity

 array(i+4)  ... BPM(k) s position along the beam line 

 array(i+5)  ... BPM(k) name(0:3)

 array(i+6)  ... BPM(k) name(4:7)

 array(i+7)  ... BPM(k) name(8:11)

 array(i+8)  ... BPM(k) name(12:15)

 array(i+9)  ... BPM(k) reserved for future use

 array(i+10) ... BPM(k+1) status (1=normal, others=error)


i=k*10,
k= 0 ... MB1R   

 = 1 ... MB2R

 = 2 ... MB3R

 
= 3 ... MB4R

 = 4 ... MB5R

 = 5 ... MB6R

 = 6 ... MB7R

 = 7 ... MB8R

 = 8 ... MB9R

 = 9 ... MB10R

 = 10 ... MB11R

 = 11 ... MB12R

 = 12,13,14 ... MB13R,MB14R,MB15R...

 = 97 ... MB98R(end)

 To change the mode of the DR

 caput DRBPM:ORBIT_MODE 1

 1 is for COD (averaging), the one needed 
 
2 is for one turn

---
 ## Notes for the mOTR

To insert/extract mOTR screens:

caput mOTR3:Target:WRITE:IN 1

caput mOTR3:Target:WRITE:OUT 1

To check the status of screen (in or out):

caget mOTR3:Target:READ:INOUT 

To Acquire images:

caget mOTR1:IMAGE:ArrayData

caput mOTR1:CAMERA:Acquire 1

caget mOTR1:IMAGE:ArrayData

Image size = 1280 x 960

To get the calibration factors

caget mOTR3:H:x1:Calibration:Factor