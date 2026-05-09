#!/usr/bin/env python3
"""
Kerala Election Live Predictor — local web server
Run: python app.py
Then open: http://localhost:5000
"""

import os, json, math, sys
from flask import Flask, jsonify, request

# ── paths ────────────────────────────────────────────────────────────────────
BASE        = os.path.dirname(__file__)
DATA_DIR    = os.path.join(BASE, "data")
PARSED_2021_DIR = os.path.join(DATA_DIR, "2021")
ROUND_2026_DIR  = os.path.join(DATA_DIR, "2026")
META_FILE   = os.path.join(DATA_DIR, "constituency_meta.json")
LIVE_FILE   = os.path.join(DATA_DIR, "live_results.json")
PRED_FILE   = os.path.join(DATA_DIR, "live_predictions.json")
DATA_PARSING_DIR = os.path.join(DATA_DIR, "data_parsing")
LIVE_FILE_LEGACY = LIVE_FILE
LIVE_FILE   = os.path.join(DATA_PARSING_DIR, "live_results.json")

# ── 2021 candidate metadata (all 140) ───────────────────────────────────────
# [no, name, district, [ldf_cand, ldf_party, ldf_votes],
#                      [udf_cand, udf_party, udf_votes],
#                      [nda_cand, nda_party, nda_votes], winner_alliance]
RAW_META = [
[1,'Manjeshwaram','Kasaragod',['V. V. Rameshan','CPI(M)',40639],['A. K. M. Ashraf','IUML',65758],['K. Surendran','BJP',65013],'udf'],
[2,'Kasaragod','Kasaragod',['M. A. Latheef','INL',28323],['N. A. Nellikkunnu','IUML',63296],['K. Sreekanth','BJP',50395],'udf'],
[3,'Udma','Kasaragod',['C. H. Kunhambu','CPI(M)',78664],['Periya Balakrishnan','INC',65342],['A. Velayudhan','BJP',20360],'ldf'],
[4,'Kanhangad','Kasaragod',['E. Chandrasekharan','CPI',84615],['P. V. Suresh','INC',57476],['M. Balraj','BJP',21570],'ldf'],
[5,'Thrikkaripur','Kasaragod',['M. Rajagopal','CPI(M)',86151],['M. P. Joseph','KC',60014],['T. V. Shibin','BJP',10961],'ldf'],
[6,'Payyanur','Kannur',['T. I. Madusoodhanan','CPI(M)',93695],['M. Pradeep Kumar','INC',43915],['K. K. Sreedharan','BJP',11308],'ldf'],
[7,'Kalliasseri','Kannur',['M. Vijin','CPI(M)',88252],['Brijesh Kumar','INC',43859],['Arun Kaithapram','BJP',11365],'ldf'],
[8,'Taliparamba','Kannur',['M. V. Govindan','CPI(M)',92870],['Abdul Rasheed V. P.','INC',70181],['Gangadharan A. P.','BJP',13058],'ldf'],
[9,'Irikkur','Kannur',['Saji Kuttiyanimattom','KC(M)',66754],['Sajeev Joseph','INC',76764],['Aniyamma Rajendran','BJP',7825],'udf'],
[10,'Azhikode','Kannur',['K. V. Sumesh','CPI(M)',65794],['K. M. Shaji','IUML',59653],['K. Ranjith','BJP',15741],'ldf'],
[11,'Kannur','Kannur',['Kadannappalli Ramachandran','Con(S)',60313],['Satheeshan Pacheni','INC',58568],['Archana Vandichal','BJP',11587],'ldf'],
[12,'Dharmadom','Kannur',['Pinarayi Vijayan','CPI(M)',95522],['C. Raghunath','INC',45399],['C. K. Padmanabhan','BJP',14623],'ldf'],
[13,'Thalassery','Kannur',['A. N. Shamseer','CPI(M)',81810],['M. P. Aravindakshan','INC',45009],['-','-',0],'ldf'],
[14,'Kuthuparamba','Kannur',['K. P. Mohanan','LJD',70626],['Pottankandi Abdulla','IUML',61085],['C. Sadanandan Master','BJP',21212],'ldf'],
[15,'Mattannur','Kannur',['K. K. Shailaja','CPI(M)',96129],['Illikkal Agasthy','RSP',35166],['Biju Elakkuzhi','BJP',18223],'ldf'],
[16,'Peravoor','Kannur',['Sakeer Hussain','CPI(M)',63534],['Sunny Joseph','INC',66706],['Smitha Jayamohan','BJP',8943],'udf'],
[17,'Mananthavady','Wayanad',['O. R. Kelu','CPI(M)',74000],['P. K. Jayalakshmi','INC',62000],['Mukundan Palliyara','BJP',18000],'ldf'],
[18,'Sulthan Bathery','Wayanad',['M. S. Viswanathan','CPI(M)',68000],['I. C. Balakrishnan','INC',55000],['C. K. Janu','JRS',30000],'ldf'],
[19,'Kalpetta','Wayanad',['M. V. Shreyams Kumar','LJD',62000],['T. Siddique','INC',61000],['T. M. Subeesh','BJP',18000],'ldf'],
[20,'Vatakara','Kozhikode',['Manayath Chandran','LJD',52000],['K. K. Rema','RMPI',53000],['M. Rajesh Kumar','BJP',20000],'udf'],
[21,'Kuttiady','Kozhikode',['K. P. Kunhahammed Kutty','CPI(M)',72000],['Parakkal Abdulla','IUML',58000],['P. P. Murali','BJP',15000],'ldf'],
[22,'Nadapuram','Kozhikode',['E. K. Vijayan','CPI',68000],['K. Praveen Kumar','INC',52000],['M. P. Rajan','BJP',12000],'ldf'],
[23,'Quilandy','Kozhikode',['Kanathil Jameela','CPI(M)',76000],['N. Subramanian','INC',50000],['N. P. Radhakrishnan','BJP',18000],'ldf'],
[24,'Perambra','Kozhikode',['T. P. Ramakrishnan','CPI(M)',80000],['C. H. Ibrahimkutty','Ind',55000],['K. V. Sudheer','BJP',16000],'ldf'],
[25,'Balussery','Kozhikode',['K. M. Sachin Dev','CPI(M)',75000],['Dharmajan Bolgatty','INC',56000],['Libin Bhaskar','BJP',22000],'ldf'],
[26,'Elathur','Kozhikode',['A. K. Saseendran','NCP',65000],['Sulfikar Mayoori','Ind',50000],['T. P. Jayachandran','BJP',30000],'ldf'],
[27,'Kozhikode North','Kozhikode',['Thottathil Raveendran','CPI(M)',70000],['K. M. Abhijith','INC',56000],['M. T. Ramesh','BJP',25000],'ldf'],
[28,'Kozhikode South','Kozhikode',['Ahamed Devarkovil','INL',45000],['P. K. Noorbeena Rasheed','IUML',72000],['Navya Haridas','BJP',28000],'udf'],
[29,'Beypore','Kozhikode',['P. A. Mohammed Riyas','CPI(M)',80000],['P. M. Niyas','INC',58000],['K. P. Prakash Babu','BJP',22000],'ldf'],
[30,'Kunnamangalam','Kozhikode',['P. T. A. Rahim','Ind',65000],['Dinesh Perumanna','Ind',55000],['V. K. Sajeevan','BJP',28000],'ldf'],
[31,'Koduvally','Kozhikode',['Karat Razak','Ind',60000],['M. K. Muneer','IUML',75000],['T. Balasoman','BJP',15000],'udf'],
[32,'Thiruvambady','Kozhikode',['Linto Joseph','CPI(M)',68000],['C. P. Cheriya Muhammed','IUML',60000],['Baby Ambat','BJP',22000],'ldf'],
[33,'Kondotty','Malappuram',['Sulaiman Haji','Ind',50000],['T. V. Ibrahim','IUML',90000],['Sheeba Unnikrishnan','BJP',10000],'udf'],
[34,'Eranad','Malappuram',['K. T. Abdurahman','Ind',48000],['P. K. Basheer','IUML',92000],['Dinesh','BJP',8000],'udf'],
[35,'Nilambur','Malappuram',['P. V. Anvar','Ind',75000],['V. V. Prakash','INC',60000],['T. K. Ashok Kumar','BJP',14000],'ldf'],
[36,'Wandoor','Malappuram',['P. Midhuna','CPI(M)',55000],['A. P. Anil Kumar','INC',48000],['P. C. Vijayan','BJP',10000],'ldf'],
[37,'Manjeri','Malappuram',['P. Dibona Nassar','CPI',40000],['U. A. Latheef','IUML',96000],['P. R. Rashmilnath','BJP',8000],'udf'],
[38,'Perinthalmanna','Malappuram',['K. P. Musthafa','Ind',46000],['Najeeb Kanthapuram','IUML',85000],['Suchithra Mattada','BJP',9000],'udf'],
[39,'Mankada','Malappuram',['T. K. Rasheed Ali','CPI(M)',52000],['Manjalamkuzhi Ali','IUML',88000],['Sajesh Elayil','BJP',8000],'udf'],
[40,'Malappuram','Malappuram',['P. Abdurahman','CPI(M)',50000],['P. Ubaidulla','IUML',90000],['Sethumadhavan','BJP',9000],'udf'],
[41,'Vengara','Malappuram',['P. Jiji','CPI(M)',48000],['P. K. Kunhalikutty','IUML',92000],['Preman','BJP',7000],'udf'],
[42,'Vallikunnu','Malappuram',['A. P. Abdul Wahab','INL',58000],['P. Abdul Hameed','IUML',88000],['Peethambaran Palat','BJP',8000],'udf'],
[43,'Tirurangadi','Malappuram',['Niyas Pulikkalakath','Ind',46000],['K. P. A. Majeed','IUML',90000],['Sathar Haji','BJP',8000],'udf'],
[44,'Tanur','Malappuram',['V. Abdurahman','NSC',50000],['P. K. Firos','IUML',88000],['Narayanan','BJP',7000],'udf'],
[45,'Tirur','Malappuram',['Gafoor P. Lillis','CPI(M)',52000],['Kurukkoli Moideen','IUML',86000],['M. Abdul Salam','BJP',8000],'udf'],
[46,'Kottakkal','Malappuram',['N. A. Muhammad Kutty','NCP',48000],['K. K. Abid Hussain Thangal','IUML',90000],['P. P. Ganesan','BJP',8000],'udf'],
[47,'Thavanur','Malappuram',['K. T. Jaleel','Ind',72000],['Firoz Kunnumparambil','INC',62000],['Ramesh Kottayipuram','BDJS',12000],'ldf'],
[48,'Ponnani','Malappuram',['P. Nandakumar','CPI(M)',58000],['A. M. Rohit','INC',50000],['Subramanian Chungappalli','BDJS',10000],'ldf'],
[49,'Thrithala','Palakkad',['M. B. Rajesh','CPI(M)',80000],['V. T. Balram','INC',65000],['Sanku T. Das','BJP',18000],'ldf'],
[50,'Pattambi','Palakkad',['Muhammed Muhsin','CPI',72000],['Riyas Mukkoli','INC',60000],['K. M. Haridas','BJP',16000],'ldf'],
[51,'Shornur','Palakkad',['P. Mammikutty','CPI(M)',75000],['T. H. Feroz Babu','INC',58000],['G. Sandeep Warrier','BJP',18000],'ldf'],
[52,'Ottapalam','Palakkad',['K. Premkumar','CPI(M)',72000],['P. Sarin','INC',60000],['P. Venugopal','BJP',20000],'ldf'],
[53,'Kongad','Palakkad',['K. Shanthakumari','CPI(M)',68000],['U. C. Raman','IUML',52000],['M. Suresh Babu','BJP',18000],'ldf'],
[54,'Mannarkkad','Palakkad',['K. P. Suresh Raj','CPI',70000],['N. Shamsudheen','IUML',62000],['B. Naseema','AIADMK',12000],'ldf'],
[55,'Malampuzha','Palakkad',['A. Prabhakaran','CPI(M)',75000],['S. K. Ananthakrishnan','INC',60000],['C. Krishnakumar','BJP',22000],'ldf'],
[56,'Palakkad','Palakkad',['C. P. Pramod','CPI(M)',68000],['Shafi Parambil','INC',62000],['E. Sreedharan','BJP',54000],'ldf'],
[57,'Tarur','Palakkad',['P. P. Sumod','CPI(M)',72000],['K. A. Sheeba','INC',58000],['K. P. Jayaprakash','BJP',16000],'ldf'],
[58,'Chittur','Palakkad',['K. Krishnankutty','JD(S)',70000],['Sumesh Achuthan','INC',58000],['V. Natesan','BJP',18000],'ldf'],
[59,'Nenmara','Palakkad',['K. Babu','CPI(M)',68000],['C. N. Vijayakrishnan','CMP(J)',52000],['A. N. Anurag','BDJS',15000],'ldf'],
[60,'Alathur','Palakkad',['K. D. Prasenan','CPI(M)',75000],['Palayam Pradeep','INC',60000],['Prashanth Sivan','BJP',18000],'ldf'],
[61,'Chelakkara','Thrissur',['K. Radhakrishnan','CPI(M)',78000],['C. C. Sreekumar','INC',62000],['Shajumon Vattekkad','BJP',22000],'ldf'],
[62,'Kunnamkulam','Thrissur',['A. C. Moideen','CPI(M)',72000],['K. Jayasankar','INC',58000],['K. K. Aneeshkumar','BJP',20000],'ldf'],
[63,'Guruvayur','Thrissur',['N. K. Akbar','CPI(M)',72000],['K. N. A. Khader','IUML',58000],['Dileep Nair','DSJP',12000],'ldf'],
[64,'Manalur','Thrissur',['Murali Perunelly','CPI(M)',68000],['Vijay Hari','INC',55000],['A. N. Radhakrishnan','BJP',18000],'ldf'],
[65,'Wadakkanchery','Thrissur',['Xavier Chittilappilly','CPI(M)',72000],['Anil Akkara','INC',62000],['T. S. Ullas Babu','BJP',20000],'ldf'],
[66,'Ollur','Thrissur',['K. Rajan','CPI',68000],['Jose Valloor','INC',58000],['B. Gopalakrishnan','BJP',22000],'ldf'],
[67,'Thrissur','Thrissur',['P. Balachandran','CPI',65000],['Padmaja Venugopal','INC',58000],['Suresh Gopi','BJP',62000],'ldf'],
[68,'Nattika','Thrissur',['C. C. Mukundan','CPI',68000],['Sunil Lalur','INC',55000],['A. K. Lochanan','BJP',18000],'ldf'],
[69,'Kaipamangalam','Thrissur',['E. T. Taison','CPI',65000],['Sobha Subin','INC',52000],['C. D. Srilal','BDJS',14000],'ldf'],
[70,'Irinjalakuda','Thrissur',['R. Bindu','CPI(M)',70000],['Thomas Unniyadan','KC',58000],['Jacob Thomas','BJP',20000],'ldf'],
[71,'Puthukkad','Thrissur',['K. K. Ramachandran','CPI(M)',68000],['Sunil Anthikad','INC',55000],['A. Nagesh','BJP',18000],'ldf'],
[72,'Chalakudy','Thrissur',['Dennis Antony','KC(M)',65000],['T. J. Saneesh Kumar Joseph','INC',60000],['Unnikrishnan','BDJS',14000],'ldf'],
[73,'Kodungallur','Thrissur',['V. R. Sunil Kumar','CPI',72000],['M. P. Jackson','INC',58000],['Santhosh Chirakulam','BJP',20000],'ldf'],
[74,'Perumbavoor','Ernakulam',['Babu Joseph','KC(M)',68000],['Eldhose Kunnappilly','INC',72000],['T. P. Sindhu Mol','BJP',18000],'udf'],
[75,'Angamaly','Ernakulam',['Jose Thettayil','JD(S)',60000],['Roji M. John','INC',65000],['K. V. Sabu','BJP',20000],'udf'],
[76,'Aluva','Ernakulam',['Shelna Nishad','CPI(M)',62000],['Anwar Sadath','INC',68000],['M. N. Gopi','BJP',22000],'udf'],
[77,'Kalamassery','Ernakulam',['P. Rajeev','CPI(M)',72000],['V. E. Gafoor','IUML',55000],['P. S. Jayarajan','BDJS',18000],'ldf'],
[78,'Paravur','Ernakulam',['M. T. Nixon','CPI',62000],['V. D. Satheesan','INC',72000],['A. B. Jayaprakash','BDJS',16000],'udf'],
[79,'Vypin','Ernakulam',['K. N. Unnikrishnan','CPI(M)',65000],['Deepak Joy','INC',60000],['K. S. Shyju','BJP',18000],'ldf'],
[80,'Kochi','Ernakulam',['K. J. Maxi','CPI(M)',58000],['Tony Chammany','INC',65000],['C. G. Rajagopal','BJP',22000],'udf'],
[81,'Thrippunithura','Ernakulam',['M. Swaraj','CPI(M)',68000],['K. Babu','INC',60000],['K. S. Radhakrishnan','BJP',22000],'ldf'],
[82,'Ernakulam','Ernakulam',['Shaji George','Ind',58000],['T. J. Vinod','INC',65000],['Padmaja S. Menon','BJP',20000],'udf'],
[83,'Thrikkakara','Ernakulam',['J. Jacob','CPI(M)',62000],['P. T. Thomas','INC',70000],['S. Saji','BJP',22000],'udf'],
[84,'Kunnathunad','Ernakulam',['P. V. Sreejin','CPI(M)',65000],['V. P. Sajeendran','INC',62000],['Renu Suresh','BJP',18000],'ldf'],
[85,'Piravom','Ernakulam',['Sindhumol Jacob','KC(M)',62000],['Anoop Jacob','KC(J)',65000],['M. A. Ashish','BJP',16000],'udf'],
[86,'Muvattupuzha','Ernakulam',['Eldo Abraham','CPI',60000],['Mathew Kuzhalnadan','INC',68000],['Jiji Joseph','BJP',20000],'udf'],
[87,'Kothamangalam','Ernakulam',['Antony John','CPI(M)',65000],['Shibu Thekkumpuram','KC',58000],['Shine K. Krishnan','BDJS',14000],'ldf'],
[88,'Devikulam','Idukki',['A. Raja','CPI(M)',72000],['D. Kumar','INC',52000],['S. Ganeshan','AIADMK',10000],'ldf'],
[89,'Udumbanchola','Idukki',['M. M. Mani','CPI(M)',68000],['E. M. Augusthy','INC',55000],['Santhosh Madhavan','BDJS',12000],'ldf'],
[90,'Thodupuzha','Idukki',['K. I. Antony','KC(M)',65000],['P. J. Joseph','KC',62000],['Shyam Raj P.','BJP',18000],'ldf'],
[91,'Idukki','Idukki',['Roshy Augustine','KC(M)',68000],['Francis George','KC',58000],['Sangeetha Viswanathan','BDJS',12000],'ldf'],
[92,'Peerumade','Idukki',['Vazhoor Soman','CPI',62000],['Syriac Thomas','INC',58000],['Srinagari Rajan','BJP',18000],'ldf'],
[93,'Pala','Kottayam',['Jose K. Mani','KC(M)',75000],['Mani C. Kappan','Ind',70000],['Prameela Devi','BJP',14000],'ldf'],
[94,'Kaduthuruthy','Kottayam',['Stephen George','KC(M)',68000],['Monce Joseph','KC',58000],['Lijinlal G.','BJP',16000],'ldf'],
[95,'Vaikom','Kottayam',['C. K. Asha','CPI',65000],['P. R. Sona','INC',58000],['Ajitha Sabu','BDJS',12000],'ldf'],
[96,'Ettumanoor','Kottayam',['V. N. Vasavan','CPI(M)',70000],['Prince Lukose','KC',58000],['T. N. Harikumar','BJP',14000],'ldf'],
[97,'Kottayam','Kottayam',['K. Anilkumar','CPI(M)',65000],['Thiruvanchoor Radhakrishnan','INC',68000],['Minerva Mohan','BJP',16000],'udf'],
[98,'Puthuppally','Kottayam',['Jaick C. Thomas','CPI(M)',62000],['Oommen Chandy','INC',72000],['N. Hari','BJP',14000],'udf'],
[99,'Changanassery','Kottayam',['Job Michael','KC(M)',68000],['V. J. Laly','KC',58000],['G. Raman Nair','BJP',14000],'ldf'],
[100,'Kanjirappally','Kottayam',['N. Jayaraj','KC(M)',68000],['Joseph Vazhackan','INC',62000],['Alphons Kannanthanam','BJP',20000],'ldf'],
[101,'Poonjar','Kottayam',['Sebastian Kulathunkal','KC(M)',58000],['Tomy Kallany','INC',52000],['M. P. Sen','BDJS',12000],'ldf'],
[102,'Aroor','Alappuzha',['Daleema Jojo','CPI(M)',65000],['Shanimol Usman','INC',62000],['Aniyappan','BDJS',12000],'ldf'],
[103,'Cherthala','Alappuzha',['P. Prasad','CPI',68000],['S. Sarath','INC',60000],['P. S. Jyothis','BDJS',14000],'ldf'],
[104,'Alappuzha','Alappuzha',['P. P. Chitharanjan','CPI(M)',72000],['K. S. Manoj','INC',62000],['R. Sandeep Vachaspathi','BJP',18000],'ldf'],
[105,'Ambalappuzha','Alappuzha',['H. Salam','CPI(M)',68000],['M. Liju','INC',58000],['Anoop Antony Joseph','BJP',16000],'ldf'],
[106,'Kuttanad','Alappuzha',['Thomas K. Thomas','NCP',65000],['Jacob Abraham','KC',60000],['Thampi Mettuthara','BDJS',14000],'ldf'],
[107,'Haripad','Alappuzha',['R. Sajilal','CPI',65000],['Ramesh Chennithala','INC',72000],['K. Soman','BJP',14000],'udf'],
[108,'Kayamkulam','Alappuzha',['U. Prathibha','CPI(M)',70000],['Aritha Babu','INC',60000],['Pradeep Lal','BDJS',14000],'ldf'],
[109,'Mavelikara','Alappuzha',['M. S. Arun Kumar','CPI(M)',68000],['K. K. Shaju','INC',58000],['Sanju','BJP',16000],'ldf'],
[110,'Chengannur','Alappuzha',['Saji Cherian','CPI(M)',72000],['M. Murali','INC',58000],['M. V. Gopakumar','BJP',20000],'ldf'],
[111,'Thiruvalla','Pathanamthitta',['Mathew T. Thomas','JD(S)',65000],['Kunju Koshy Paul','KC',62000],['Ashokan Kulanada','BJP',16000],'ldf'],
[112,'Ranni','Pathanamthitta',['Pramod Narayan','KC(M)',65000],['Ringoo Cherian','INC',58000],['Padmakumar K.','BDJS',14000],'ldf'],
[113,'Aranmula','Pathanamthitta',['Veena George','CPI(M)',68000],['K. Sivadasan Nair','INC',60000],['Biju Mathew','BJP',16000],'ldf'],
[114,'Konni','Pathanamthitta',['K. U. Jenish Kumar','CPI(M)',70000],['Robin Peter','INC',58000],['K. Surendran','BJP',32000],'ldf'],
[115,'Adoor','Pathanamthitta',['Chittayam Gopakumar','CPI',66569],['M. G. Kannan','INC',34280],['Pandalam Prathapan','BJP',23980],'ldf'],
[116,'Karunagapally','Kollam',['R. Ramachandran','CPI',65017],['C. R. Mahesh','INC',42000],['Bitty Sudheer','BJP',12144],'ldf'],
[117,'Chavara','Kollam',['Sujith Vijayan','Ind',62000],['Shibu Baby John','RSP',62186],['Vivek Gopan','BJP',14211],'udf'],
[118,'Kunnathur','Kollam',['Kovoor Kunjumon','Ind',69531],['Ullas Kovoor','RSP',66522],['Raji Prasad','BJP',18000],'ldf'],
[119,'Kottarakkara','Kollam',['K. N. Balagopal','CPI(M)',68770],['Resmi R.','INC',56000],['Vayakkal Soman','BJP',16000],'ldf'],
[120,'Pathanapuram','Kollam',['K. B. Ganesh Kumar','KC(B)',65000],['Jyothikumar Chamakkala','INC',55000],['Jithin Dev','BJP',18000],'ldf'],
[121,'Punalur','Kollam',['P. S. Supal','CPI',65000],['Abdurahman Randathani','IUML',52000],['Ayoor Murali','BJP',18000],'ldf'],
[122,'Chadayamangalam','Kollam',['J. Chinchu Rani','CPI',65000],['M. M. Naseer','INC',52000],['Vishnu Pattathanam','BJP',16000],'ldf'],
[123,'Kundara','Kollam',['J. Mercykutty Amma','CPI(M)',70000],['P. C. Vishnunath','INC',58000],['Vanaja Vidyadharan','BDJS',14000],'ldf'],
[124,'Kollam','Kollam',['Mukesh','CPI(M)',72000],['Bindhu Krishna','INC',60000],['M. Sunil','BJP',18000],'ldf'],
[125,'Eravipuram','Kollam',['M. Noushad','CPI(M)',68000],['Babu Divakaran','RSP',58000],['Ranjith Raveendran','BDJS',14000],'ldf'],
[126,'Chathannur','Kollam',['G. S. Jayalal','CPI',59296],['N. Peethambarakurup','INC',34280],['B. B. Gopakumar','BJP',42090],'ldf'],
[127,'Varkala','Thiruvananthapuram',['V. Joy','CPI(M)',68000],['B. R. M. Shafeer','INC',56000],['Aji S. R. M.','BDJS',14000],'ldf'],
[128,'Attingal','Thiruvananthapuram',['O. S. Ambika','CPI(M)',69898],['A. Sreedharan','RSP',36938],['P. Sudheer','BJP',26000],'ldf'],
[129,'Chirayinkeezhu','Thiruvananthapuram',['V. Sasi','CPI',62634],['Anup B.S.','INC',52000],['Ashanath','BJP',22000],'ldf'],
[130,'Nedumangad','Thiruvananthapuram',['G. R. Anil','CPI',72742],['P. S. Prasanth','INC',58000],['J. R. Padmakumar','BJP',26861],'ldf'],
[131,'Vamanapuram','Thiruvananthapuram',['D. K. Murali','CPI(M)',73137],['Anad Jayan','INC',62895],['Thazhava Sahadevan','BDJS',16000],'ldf'],
[132,'Kazhakkoottam','Thiruvananthapuram',['Kadakampally Surendran','CPI(M)',72000],['S. S. Lal','INC',58000],['Shobha Surendran','BJP',42000],'ldf'],
[133,'Vattiyoorkavu','Thiruvananthapuram',['V. K. Prasanth','CPI(M)',68000],['Veena S. Nair','INC',62000],['V. V. Rajesh','BJP',30000],'ldf'],
[134,'Thiruvananthapuram','Thiruvananthapuram',['Antony Raju','JKC',68000],['V. S. Sivakumar','INC',62000],['Krishna Kumar','BJP',40000],'ldf'],
[135,'Nemom','Thiruvananthapuram',['V. Sivankutty','CPI(M)',72000],['K. Muraleedharan','INC',60000],['Kummanam Rajasekharan','BJP',60000],'ldf'],
[136,'Aruvikkara','Thiruvananthapuram',['G. Stephen','CPI(M)',65000],['K. S. Sabarinathan','INC',58000],['C. Sivankutty','BJP',24000],'ldf'],
[137,'Parassala','Thiruvananthapuram',['C. K. Hareendran','CPI(M)',68000],['Ansajitha Ressal','INC',56000],['Karamana Jayan','BJP',22000],'ldf'],
[138,'Kattakkada','Thiruvananthapuram',['I. B. Sathish','CPI(M)',70000],['Malayinkeezhu Venugopal','INC',60000],['P. K. Krishnadas','BJP',24000],'ldf'],
[139,'Kovalam','Thiruvananthapuram',['Neelalohithadasan Nadar','JD(S)',65000],['M. Vincent','INC',62000],['Vishnupuram Chandrasekharan','KKC',12000],'ldf'],
[140,'Neyyattinkara','Thiruvananthapuram',['K. Ansalan','CPI(M)',68000],['R. Selvaraj','INC',58000],['Rajasekharan S Nair','BJP',22000],'ldf'],
]

def _load_cands_2026_data(dir26):
    """Build a per-constituency dict {cno_str: {name, district, ldf, udf, nda}} from 2026 folder."""
    out = {}
    if not os.path.isdir(dir26):
        return out
    for fname in os.listdir(dir26):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(dir26, fname), encoding="utf-8") as f:
            e = json.load(f)
        cno = str(e["const_no"])
        row = {"name": e.get("name", ""), "district": e.get("district", "")}
        for cand in e.get("candidates_2026", []):
            a = cand.get("alliance")
            if a in ("ldf", "udf", "nda") and cand.get("is_major_alliance"):
                row[a] = {"name": cand["name"], "party": cand.get("party", "")}
        for a in ("ldf", "udf", "nda"):
            row.setdefault(a, {"name": "", "party": ""})
        out[cno] = row
    return out

# ── load 2026 candidate data ──────────────────────────────────────────────────
CANDS_2026_DATA = _load_cands_2026_data(ROUND_2026_DIR)
if CANDS_2026_DATA:
    filled = sum(1 for v in CANDS_2026_DATA.values()
                 if v["ldf"]["name"] or v["udf"]["name"] or v["nda"]["name"])
    print(f"[OK] Loaded 2026 candidates ({filled}/{len(CANDS_2026_DATA)} constituencies filled)")

# ── build meta dict ──────────────────────────────────────────────────────────
META = {}
for row in RAW_META:
    no, name, dist, ldf, udf, nda, winner = row
    c26 = CANDS_2026_DATA.get(str(no), {})

    def _cand(alliance, data2021, key):
        c = c26.get(key, {})
        n = c.get("name", "").strip()
        p = c.get("party", "").strip()
        return {
            "name":      n if n else data2021[0],
            "party":     p if p else data2021[1],
            "alliance":  alliance,
            "actual2021": data2021[2],
            "is_2026":   bool(n),
        }

    cands = [
        _cand("ldf", ldf, "ldf"),
        _cand("udf", udf, "udf"),
        _cand("nda", nda, "nda"),
    ]
    META[no] = {
        "no": no, "name": name, "district": dist,
        "candidates": cands, "winner2021": winner
    }

# ── load parsed PDF data if available ───────────────────────────────────────
BOOTH_DATA = {}
if os.path.isdir(PARSED_2021_DIR):
    for fname in os.listdir(PARSED_2021_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(PARSED_2021_DIR, fname), encoding="utf-8") as f:
            entry = json.load(f)
        BOOTH_DATA[int(entry["const_no"])] = entry
    print(f"[OK] Loaded 2021 booth-wise data for {len(BOOTH_DATA)} constituencies from split files")
else:
    print("[!]  No parsed PDF data found. Run parse_pdfs.py && split_2021_booth_data.py")

# ── build booth counts from year folders ─────────────────────────────────────
BOOTHS_COUNT_2021 = {
    str(no): entry["booth_summary"]["main_booths"]
    for no, entry in BOOTH_DATA.items()
    if entry.get("booth_summary", {}).get("main_booths")
}
if BOOTHS_COUNT_2021:
    print(f"[OK] Built 2021 booth counts for {len(BOOTHS_COUNT_2021)} constituencies from 2021 folder")

BOOTHS_COUNT_2026 = {}
VPOLL_DATA = {}
VPOLL_FILE = os.path.join(DATA_PARSING_DIR, "votes_polled.json")
if os.path.exists(VPOLL_FILE):
    with open(VPOLL_FILE, encoding="utf-8") as _f:
        VPOLL_DATA = json.load(_f)
if os.path.isdir(ROUND_2026_DIR):
    for _fname in os.listdir(ROUND_2026_DIR):
        if not _fname.endswith(".json"):
            continue
        with open(os.path.join(ROUND_2026_DIR, _fname), encoding="utf-8") as _f:
            _e = json.load(_f)
        _cno = str(_e["const_no"])
        if _e.get("booth_count"):
            BOOTHS_COUNT_2026[_cno] = _e["booth_count"]
        if _e.get("turnout"):
            VPOLL_DATA.setdefault(_cno, {}).update(_e["turnout"])
            for _key in ("male", "female", "male_polled", "female_polled"):
                if _e.get(_key) is not None:
                    VPOLL_DATA[_cno][_key] = _e.get(_key)
    if BOOTHS_COUNT_2026:
        print(f"[OK] Built 2026 booth counts for {len(BOOTHS_COUNT_2026)} constituencies from 2026 folder")
    if VPOLL_DATA:
        print(f"[OK] Loaded votes-polled data for {len(VPOLL_DATA)} constituencies")

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)


def historical_alliance_refs(year, const_no):
    """Return historical alliance reference rows from split year JSON."""
    path = os.path.join(DATA_DIR, str(year), f"{const_no:03d}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    refs = {}
    for cand in entry.get(f"candidates_{year}", []):
        alliance = cand.get("alliance")
        if alliance not in ("ldf", "udf", "nda") or alliance in refs:
            continue
        refs[alliance] = {
            "name": cand.get("name", ""),
            "party": cand.get("party", ""),
            "votes": cand.get(f"actual_votes_{year}", 0),
        }
    return refs


def historical_ls_refs(ls_year, const_no):
    """Return LS election alliance vote totals for an assembly segment."""
    dir_name = f"{ls_year}_ls"
    path = os.path.join(DATA_DIR, dir_name, f"{const_no:03d}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    totals = entry.get("booth_summary", {}).get("candidate_totals", [])
    if not totals:
        return {}
    cands_key = f"candidates_{ls_year}_ls"
    refs = {}
    for cand in entry.get(cands_key, []):
        idx = cand.get("index", -1)
        raw_alliance = (cand.get("alliance") or "").lower()
        if raw_alliance not in ("ldf", "udf", "nda") or raw_alliance in refs:
            continue
        votes = totals[idx] if 0 <= idx < len(totals) else 0
        refs[raw_alliance] = {
            "name": cand.get("name", ""),
            "party": cand.get("party", ""),
            "votes": votes,
        }
    return refs


@app.route("/api/constituencies")
def get_constituencies():
    """Return full metadata for all 140 constituencies with 2026 booth data prioritized."""
    # Reload 2026 candidate data fresh on each call so edits take effect immediately
    c26_fresh = _load_cands_2026_data(ROUND_2026_DIR)

    def _fresh_cand(alliance, data2021, c26_entry, key):
        c = c26_entry.get(key, {})
        n = c.get("name", "").strip()
        p = c.get("party", "").strip()
        return {
            "name":       n if n else data2021[0],
            "party":      p if p else data2021[1],
            "alliance":   alliance,
            "actual2021": data2021[2],
            "party2021":  data2021[1],
            "name2021":   data2021[0],
            "is_2026":    bool(n),
        }

    result = []
    for no, meta in sorted(META.items()):
        entry = dict(meta)
        # Re-apply fresh candidate data from disk
        raw_row = next((r for r in RAW_META if r[0] == no), None)
        if raw_row:
            _no, _nm, _dist, ldf21, udf21, nda21, _win = raw_row
            c26e = c26_fresh.get(str(no), {})
            entry["candidates"] = [
                _fresh_cand("ldf", ldf21, c26e, "ldf"),
                _fresh_cand("udf", udf21, c26e, "udf"),
                _fresh_cand("nda", nda21, c26e, "nda"),
            ]
        refs2016 = historical_alliance_refs(2016, no)
        refs2021 = historical_alliance_refs(2021, no)
        refs2011 = historical_alliance_refs(2011, no)
        refs2019ls = historical_ls_refs(2019, no)
        refs2024ls = historical_ls_refs(2024, no)
        votes2026 = historical_alliance_refs(2026, no)
        for cand in entry["candidates"]:
            alliance = cand["alliance"]
            ref11 = refs2011.get(alliance, {})
            ref16 = refs2016.get(alliance, {})
            ref21 = refs2021.get(alliance, {})
            ref19ls = refs2019ls.get(alliance, {})
            ref24ls = refs2024ls.get(alliance, {})
            if ref11:
                cand["actual2011"] = ref11.get("votes", 0)
                cand["party2011"] = ref11.get("party", "")
                cand["name2011"] = ref11.get("name", "")
            if ref16:
                cand["actual2016"] = ref16.get("votes", 0)
                cand["party2016"] = ref16.get("party", "")
                cand["name2016"] = ref16.get("name", "")
            if ref21:
                cand["actual2021"] = ref21.get("votes", cand.get("actual2021", 0))
                cand["party2021"] = ref21.get("party", cand.get("party2021", ""))
                cand["name2021"] = ref21.get("name", cand.get("name2021", ""))
            if ref19ls:
                cand["actual2019ls"] = ref19ls.get("votes", 0)
                cand["party2019ls"] = ref19ls.get("party", "")
                cand["name2019ls"] = ref19ls.get("name", "")
            if ref24ls:
                cand["actual2024ls"] = ref24ls.get("votes", 0)
                cand["party2024ls"] = ref24ls.get("party", "")
                cand["name2024ls"] = ref24ls.get("name", "")
            v26 = votes2026.get(alliance)
            if v26 is not None:
                cand["actual2026"] = v26.get("votes", 0)
        bd = BOOTH_DATA.get(no)
        
        # Load booth count data for 2021 and 2026
        const_no_str = str(no)
        booths_2021 = BOOTHS_COUNT_2021.get(const_no_str)
        booths_2026 = BOOTHS_COUNT_2026.get(const_no_str)
        
        # ── Determine booth counts: prioritize 2026 data ──────────────────────
        # Use 2026 counts if available, fallback to 2021, then to PDF estimates
        if booths_2026:
            # Use 2026 official booth count
            total_main_booths = booths_2026
            total_rounds = math.ceil(booths_2026 / 14)
            has_2026_data = True
        elif booths_2021:
            # Use 2021 booth count (no 2026 data yet)
            total_main_booths = booths_2021
            total_rounds = math.ceil(booths_2021 / 14)
            has_2026_data = False
        elif bd:
            # Fallback to PDF data if neither 2021 nor 2026 count available
            main_booths = sorted({b["main"] for b in bd["booths"] if not b["is_aux"]})
            total_main_booths = len(main_booths)
            total_rounds = math.ceil(len(main_booths) / 14)
            has_2026_data = False
        else:
            # Estimate from 2021 vote totals
            total_votes = sum(c["actual2021"] for c in meta["candidates"])
            total_main_booths = max(round(total_votes / 430), 150)
            total_rounds = math.ceil(total_main_booths / 14)
            has_2026_data = False
        
        # Set booth info in response
        round_results_rounds = eci_round_count(no)
        if round_results_rounds:
            total_rounds = max(total_rounds, round_results_rounds)
        entry["total_main_booths"] = total_main_booths
        entry["total_rounds"] = total_rounds
        entry["booth_derived_rounds"] = math.ceil(total_main_booths / 14)
        entry["round_results_rounds"] = round_results_rounds
        entry["has_2026_data"] = has_2026_data
        if const_no_str in VPOLL_DATA:
            vpd = VPOLL_DATA[const_no_str]
            for gender_key in ("male", "female", "male_polled", "female_polled"):
                if vpd.get(gender_key) is not None:
                    entry[gender_key] = vpd.get(gender_key)
        
        # Add PDF candidate data if available
        if bd and bd.get("booths"):
            entry["total_booths_including_aux"] = len(bd["booths"])
            entry["pdf_candidates"] = bd.get("candidates", [])
            entry["has_pdf_data"] = True
        else:
            entry["total_booths_including_aux"] = total_main_booths
            entry["pdf_candidates"] = []
            entry["has_pdf_data"] = False
        
        # Add historical booth count data
        entry["booth_2021"] = booths_2021
        entry["booth_2026"] = booths_2026
        if booths_2021 and booths_2026:
            entry["booth_change"] = booths_2026 - booths_2021
            entry["booth_change_pct"] = round((booths_2026 - booths_2021) / booths_2021 * 100, 1)
            entry["booth_scaling_factor"] = round(booths_2026 / booths_2021, 3)
        
        result.append(entry)
    return jsonify(result)

@app.route("/api/booth_data/<int:const_no>")
def get_booth_data(const_no):
    """Return full booth-level 2021 data for a constituency (for 2021 backtesting)."""
    bd = BOOTH_DATA.get(const_no)
    if not bd or not bd.get("booths"):
        return jsonify({"error": "No booth-wise data for this constituency"}), 404

    meta = META.get(const_no, {})
    # Group booths by round (count only main booths)
    booths = bd["booths"]
    main_nos = sorted({b["main"] for b in booths if not b["is_aux"]})

    rounds = []
    for r_idx in range(math.ceil(len(main_nos) / 14)):
        chunk = main_nos[r_idx*14 : r_idx*14+14]
        chunk_set = set(chunk)
        round_booths = [b for b in booths if b["main"] in chunk_set]
        # sum votes per candidate
        n_cands = max((len(b["votes"]) for b in round_booths), default=0)
        totals = [sum(b["votes"][i] if i < len(b["votes"]) else 0 for b in round_booths)
                  for i in range(n_cands)]
        rounds.append({
            "round": r_idx + 1,
            "main_booths": chunk,
            "booth_count": len(round_booths),
            "votes": totals,
        })

    return jsonify({
        "const_no": const_no,
        "name": meta.get("name", bd.get("name", "")),
        "pdf_candidates": bd.get("candidates", []),
        "candidates": meta.get("candidates", []),
        "rounds": rounds,
        "total_main_booths": len(main_nos),
    })

def compute_historical_distribution_shift(const_no, current_pct, votes_in, bd):
    """
    Compute vote distribution shift pattern from 2021 historical data.
    
    Strategy:
    1. Find the round in 2021 where counted percentage ≈ current_pct
    2. Get candidate vote distributions at that round and final
    3. Calculate shift pattern: how votes changed from that point to end
    4. Apply shift to current votes for improved prediction
    
    Returns: (shift_factors, historical_pct) or (None, None) if not available
    """
    if not bd:
        return None, None
    
    booths = bd["booths"]
    main_nos = sorted({b["main"] for b in booths if not b["is_aux"]})
    total_main = len(main_nos)
    
    # Find historical reference point closest to current_pct
    best_round_idx = None
    best_pct_diff = float('inf')
    
    for r_idx in range(len(main_nos) // 14 + 1):
        cutoff_count = min((r_idx + 1) * 14, total_main)
        hist_pct = cutoff_count / total_main if total_main > 0 else 0
        pct_diff = abs(hist_pct - current_pct)
        
        if pct_diff < best_pct_diff:
            best_pct_diff = pct_diff
            best_round_idx = r_idx
    
    if best_round_idx is None or best_pct_diff > 0.15:  # Must be within 15% of current
        return None, None
    
    # Get votes at historical reference round
    cutoff_count = min((best_round_idx + 1) * 14, total_main)
    cutoff_booths = main_nos[:cutoff_count]
    cutoff_set = set(cutoff_booths)
    hist_round_booths = [b for b in booths if b["main"] in cutoff_set]
    
    n_cands = max((len(b["votes"]) for b in hist_round_booths), default=0)
    if n_cands != len(votes_in):
        return None, None
    
    # Calculate distributions at historical reference point and final
    hist_totals = [sum(b["votes"][i] if i < len(b["votes"]) else 0 
                       for b in hist_round_booths) for i in range(n_cands)]
    final_totals = [sum(b["votes"][i] if i < len(b["votes"]) else 0 
                        for b in booths) for i in range(n_cands)]
    
    hist_total = sum(hist_totals)
    final_total = sum(final_totals)
    
    if hist_total == 0:
        return None, None
    
    # Calculate distribution shift (percentage-point change)
    hist_dist = [h / hist_total for h in hist_totals]
    final_dist = [f / final_total for f in final_totals]
    shift = [final_dist[i] - hist_dist[i] for i in range(n_cands)]
    
    hist_pct = cutoff_count / total_main if total_main > 0 else 0
    
    return shift, hist_pct


@app.route("/api/predict", methods=["POST"])
def predict():
    """
    POST body: { const_no, booths_counted, total_main_booths, votes: [v0,v1,v2] }
    Uses the same share-shift prediction engine as predict_from_eci.py, with
    vote-based pct = sum(votes) / votes_polled so projections stay within the
    known total votes cast (never overshoots votes_polled).
    """
    data           = request.json
    const_no       = data.get("const_no")
    booths_counted = max(int(data.get("booths_counted", 0)), 1)
    total_main     = int(data.get("total_main_booths", 200))
    votes_in       = [int(v) for v in data.get("votes", [])]

    if not votes_in or sum(votes_in) == 0:
        return jsonify({"error": "No votes entered"}), 400

    meta      = META.get(const_no, {})
    cands     = meta.get("candidates", [])
    tot_rounds = int(data.get("total_rounds") or math.ceil(total_main / 14) or 1)

    # Prefer explicit UI round; fall back to deriving from booth count.
    if data.get("current_round"):
        cur_round = max(1, min(int(data.get("current_round")), tot_rounds))
    else:
        booths_per_round = max(1, math.ceil(total_main / tot_rounds))
        cur_round = max(1, min(math.ceil(booths_counted / booths_per_round), tot_rounds))

    # Vote-based pct: use actual votes counted vs total votes polled
    vp_entry      = VPOLL_DATA.get(str(const_no), {})
    votes_polled_v = vp_entry.get("votes_polled", 0)
    total_counted  = sum(votes_in)   # approximation (excludes minor independents)

    # Import the canonical prediction engine (cached after first import)
    from predict_from_eci import (
        predict as eci_predict,
        assess_call_readiness,
        projected_winner_history_from_2026,
        shift_pattern_history_from_2026,
        summarize_shift_stability,
        call_readiness_timeline_from_2026,
    )
    pred = eci_predict(votes_in, cur_round, tot_rounds,
                       const_no=const_no,
                       votes_polled=votes_polled_v,
                       total_counted=total_counted)

    if not pred:
        return jsonify({"error": "Prediction failed"}), 500

    projected  = pred["projected"]
    total_proj = pred["total_projected"]

    # Hard cap: projection must not exceed votes_polled
    if votes_polled_v > 0 and total_proj > votes_polled_v:
        scale     = votes_polled_v / total_proj
        projected  = [round(v * scale) for v in projected]
        total_proj = sum(projected)

    w_idx = pred["winner_idx"]
    winner_alliance = cands[w_idx]["alliance"] if w_idx < len(cands) else "ldf"
    shift_patterns = shift_pattern_history_from_2026(const_no, cur_round)
    projected_rank = pred.get("projected", []) or votes_in
    top_indices = sorted(range(len(projected_rank)), key=lambda i: -projected_rank[i])[:3]
    call_timeline = call_readiness_timeline_from_2026(const_no, cur_round)
    pred.update(assess_call_readiness(
        pred,
        cur_round,
        tot_rounds,
        votes_in,
        projected_winner_history_from_2026(const_no, cur_round),
        shift_patterns,
    ))

    return jsonify({
        "projected":        projected,
        "total_projected":  total_proj,
        "winner_idx":       w_idx,
        "winner_alliance":  winner_alliance,
        "margin":           pred["margin"],
        "confidence":       pred["confidence"],
        "call_status":      pred.get("call_status", "watching"),
        "call_label":       pred.get("call_label", "Watching Trend"),
        "call_confidence":  pred.get("call_confidence", "Medium"),
        "call_confidence_pct": pred.get("call_confidence_pct", pred["confidence"]),
        "raw_confidence":   pred.get("raw_confidence"),
        "call_ready":       pred.get("call_ready", False),
        "call_reason":      pred.get("call_reason", ""),
        "pct_counted":      pred["pct_counted"],
        "used_pdf_pattern": pred["used_pattern"],
        "booth_info":       {"scaling": 1.0},
        "votes_counted":    total_counted,
        "votes_polled":     votes_polled_v,
        "formula":          pred.get("formula", {}),
        "shift_patterns":   shift_patterns,
        "shift_stability":  summarize_shift_stability(shift_patterns, top_indices),
        "call_timeline":    call_timeline,
        "ready_since_round": call_timeline.get("ready_since_round"),
    })

@app.route("/api/live_results")
def get_live_results():
    """Return ECI-style live round-wise results built from 2026 split files."""
    from predict_from_eci import build_live_results_from_2026
    data = build_live_results_from_2026()
    if not data:
        return jsonify({"error": "No 2026 round data available"}), 404
    return jsonify(data)


@app.route("/api/live_predictions")
def get_live_predictions():
    """Return auto-computed predictions. If stale/missing, regenerates inline."""
    # Auto-regenerate if missing or if any 2026 split file is newer.
    should_regen = not os.path.exists(PRED_FILE)
    if not should_regen and os.path.isdir(ROUND_2026_DIR):
        pred_mtime = os.path.getmtime(PRED_FILE)
        for fname in os.listdir(ROUND_2026_DIR):
            if fname.endswith(".json") and os.path.getmtime(os.path.join(ROUND_2026_DIR, fname)) > pred_mtime:
                should_regen = True
                break
    if should_regen:
        try:
            sys.path.insert(0, BASE)
            from predict_from_eci import run as predict_run
            predict_run()
        except Exception as e:
            print(f"[predict] inline regen failed: {e}")
    if not os.path.exists(PRED_FILE):
        return jsonify({"error": "No predictions yet. Run predict_from_eci.py"}), 404
    with open(PRED_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/live_results/<int:const_no>")
def get_live_result(const_no):
    """Return ECI-style data for one constituency with round-wise breakdown."""
    from predict_from_eci import build_live_results_from_2026
    data = build_live_results_from_2026()
    result = data.get(str(const_no))
    if not result:
        return jsonify({"error": "No data for this constituency"}), 404

    meta = META.get(const_no, {})
    total_main   = BOOTHS_COUNT_2026.get(str(const_no)) or BOOTHS_COUNT_2021.get(str(const_no)) or 200
    booth_rounds = math.ceil(total_main / 14)
    eci_rounds = int(result.get("tot_rounds", 0) or 0)
    round_results_rounds = eci_round_count(const_no)
    total_rounds = max(booth_rounds, eci_rounds, round_results_rounds)

    return jsonify({
        "const_no":      const_no,
        "name":          meta.get("name", ""),
        "district":      meta.get("district", ""),
        "candidates_app": meta.get("candidates", []),
        "total_main_booths": total_main,
        "total_rounds":  total_rounds,
        "booth_derived_rounds": booth_rounds,
        "round_results_rounds": round_results_rounds,
        **result,
    })


@app.route("/api/votes_polled")
def get_votes_polled():
    if not VPOLL_DATA:
        return jsonify({}), 404
    return jsonify(VPOLL_DATA)


def load_round_result(const_no):
    """Load 2026 round result from data/2026 split files."""
    split_path = os.path.join(ROUND_2026_DIR, f"{const_no:03d}.json")
    if os.path.exists(split_path):
        with open(split_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def eci_round_count(const_no):
    """Return the number of round rows available from saved 2026 ECI round data."""
    rr = load_round_result(const_no)
    if not rr:
        return 0
    rounds = rr.get("rounds", [])
    if not rounds:
        return 0
    return max((int(r.get("round", 0)) for r in rounds), default=len(rounds))


def _norm_name_for_match(value):
    import re as _re
    return _re.sub(r"[^a-z]", "", (value or "").lower())


def _name_overlap_score(left, right):
    left_n = _norm_name_for_match(left)
    right_n = _norm_name_for_match(right)
    score = 0
    for length in range(4, min(len(left_n), len(right_n)) + 1):
        for i in range(len(left_n) - length + 1):
            if left_n[i:i + length] in right_n:
                score = max(score, length)
    return score


def _classify_2026_leader(candidate_name, party, meta_entry):
    """Classify a 2026 ECI candidate as ldf/udf/nda/other."""
    try:
        from predict_from_eci import eci_party_alliance
        known = eci_party_alliance(party or "")
        if known:
            return known
    except Exception:
        pass

    best_alliance, best_score = "other", 0
    for cand in meta_entry.get("candidates", []):
        score = _name_overlap_score(candidate_name, cand.get("name", ""))
        if score > best_score:
            best_score = score
            best_alliance = cand.get("alliance", "other")
    return best_alliance if best_score >= 5 else "other"


@app.route("/api/round_leads_matrix")
def get_round_leads_matrix():
    """Return cumulative leading alliance by round for every constituency."""
    rows = []
    max_round = 0
    const_delta_leads = {}  # const_no -> {round_no: alliance}

    for const_no in sorted(META):
        result = load_round_result(const_no)
        meta = META[const_no]
        if not result:
            rows.append({
                "const_no": const_no,
                "name": meta["name"],
                "district": meta["district"],
                "rounds": [],
            })
            continue

        candidates = result.get("candidates", [])
        parties = result.get("parties", [])
        # Build a direct idx→alliance map from candidates_2026 (authoritative)
        cands_2026 = result.get("candidates_2026", [])
        idx_alliance = {}
        for i, c in enumerate(cands_2026):
            a = c.get("alliance", "other")
            idx = c.get("index", i)
            idx_alliance[idx] = a if a in ("ldf", "udf", "nda") else "other"
        row_rounds = []
        delta_leads = {}

        for rr in result.get("rounds", []):
            round_no = int(rr.get("round", len(row_rounds) + 1))
            cumulative = rr.get("cumulative", [])
            if not cumulative:
                continue
            lead_idx = max(range(len(cumulative)), key=lambda i: cumulative[i])
            leader_name = candidates[lead_idx] if lead_idx < len(candidates) else ""
            leader_party = parties[lead_idx] if lead_idx < len(parties) else ""
            # Use direct candidates_2026 alliance if available, else fall back to name matching
            if lead_idx in idx_alliance:
                alliance = idx_alliance[lead_idx]
            else:
                alliance = _classify_2026_leader(leader_name, leader_party, meta)

            round_entry = {
                "round": round_no,
                "alliance": alliance,
                "leader_name": leader_name,
                "leader_party": leader_party,
                "votes": cumulative[lead_idx],
            }
            max_round = max(max_round, round_no)

            # Per-round delta leader using the increment field directly
            increment = rr.get("increment", [])
            if increment and any(v > 0 for v in increment):
                inc_lead_idx = max(range(len(increment)), key=lambda x: increment[x])
                inc_leader_name = candidates[inc_lead_idx] if inc_lead_idx < len(candidates) else ""
                inc_leader_party = parties[inc_lead_idx] if inc_lead_idx < len(parties) else ""
                inc_alliance = idx_alliance.get(inc_lead_idx, "other")
                delta_leads[round_no] = inc_alliance
                round_entry.update({
                    "delta_alliance": inc_alliance,
                    "delta_leader_name": inc_leader_name,
                    "delta_leader_party": inc_leader_party,
                    "delta_votes": increment[inc_lead_idx],
                })

            row_rounds.append(round_entry)

        const_delta_leads[const_no] = delta_leads

        rows.append({
            "const_no": const_no,
            "name": meta["name"],
            "district": meta["district"],
            "rounds": row_rounds,
        })

    # Some constituencies finish earlier than the statewide maximum round.
    # Carry their final leader forward so the statewide line chart remains a
    # 140-seat snapshot at every round instead of shrinking as seats complete.
    tally_by_round = {}
    for row in rows:
        by_round = {int(rr["round"]): rr for rr in row["rounds"]}
        carried_rounds = []
        last_seen = None
        for round_no in range(1, max_round + 1):
            if round_no in by_round:
                last_seen = {**by_round[round_no], "carried": False}
            elif last_seen:
                last_seen = {**last_seen, "round": round_no, "carried": True}
            else:
                continue

            carried_rounds.append(last_seen)
            tally = tally_by_round.setdefault(
                str(round_no), {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
            )
            alliance = last_seen.get("alliance", "other")
            tally[alliance] = tally.get(alliance, 0) + 1
        row["rounds"] = carried_rounds

    # delta_tally_by_round: count which alliance led per round (no carry-forward)
    delta_tally_by_round = {}
    for const_no, delta_leads in const_delta_leads.items():
        for round_no, alliance in delta_leads.items():
            tally = delta_tally_by_round.setdefault(
                str(round_no), {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
            )
            tally[alliance] = tally.get(alliance, 0) + 1

    return jsonify({
        "max_round": max_round,
        "tally_by_round": tally_by_round,
        "delta_tally_by_round": delta_tally_by_round,
        "rows": rows,
    })


@app.route("/api/round_results/<int:const_no>")
def get_round_results(const_no):
    """Return per-round candidate vote data with 2021 alliance comparison."""
    result = load_round_result(const_no)
    if not result:
        return jsonify({"error": "No round data for this constituency"}), 404

    candidate_alliances = ["other" for _ in result.get("candidates", [])]
    for cand in result.get("candidates_2026", []):
        idx = cand.get("index")
        alliance = (cand.get("alliance") or "other").lower()
        if isinstance(idx, int) and 0 <= idx < len(candidate_alliances):
            candidate_alliances[idx] = alliance if alliance in ("ldf", "udf", "nda") else "other"

    # Load supporting data for 2021 comparison
    bd = BOOTH_DATA.get(const_no)

    pred_map = {}
    if os.path.exists(PRED_FILE):
        with open(PRED_FILE, encoding="utf-8") as f:
            pred_map = (json.load(f).get("predictions", {})
                        .get(str(const_no), {})
                        .get("candidates_mapped", {}))

    tot_rounds = result.get("tot_rounds", 0)

    # Without booth data, predictions or tot_rounds, return as-is
    if not bd or not pred_map or not tot_rounds:
        return jsonify({**result, "candidate_alliances": candidate_alliances})

    import re as _re
    def _norm(s):
        return _re.sub(r'[^a-z]', '', s.lower())

    candidates = result.get("candidates", [])
    rounds     = result.get("rounds", [])

    # Map each alliance to the index in round_results.candidates[]
    alliance_idx = {}
    for alliance in ('ldf', 'udf', 'nda'):
        eci_name = pred_map.get(alliance, {}).get("eci_name", "")
        if not eci_name or eci_name == '?':
            alliance_idx[alliance] = None
            continue
        prefix = _norm(eci_name)[:8]
        best_i = next(
            (i for i, nm in enumerate(candidates) if prefix and prefix in _norm(nm)),
            None
        )
        alliance_idx[alliance] = best_i

    # 2021 booth data — candidates stored in PDF order, not ldf/udf/nda order.
    # Map alliance → booth candidate index via name matching against META.
    try:
        from predict_from_eci import clean_booths as _clean_hist_booths
        booths = _clean_hist_booths(bd.get("booths", []))
    except Exception:
        booths = [
            b for b in bd.get("booths", [])
            if 1 <= int(b.get("main", 0)) <= 500 and sum(b.get("votes", [])) <= 2000
        ]
    booth_cands   = bd.get("candidates", [])
    main_nos      = sorted({b["main"] for b in booths if not b.get("is_aux", False)})

    # Use 2021 candidate names from RAW_META (booth_wise_parsed uses 2021 data)
    raw_row = next((r for r in RAW_META if r[0] == const_no), None)
    booth_ali_idx = {}   # alliance → index in booth_cands (2021 votes)
    if raw_row:
        _no, _nm, _dist, ldf21, udf21, nda21, _win = raw_row
        names_2021 = {'ldf': ldf21[0], 'udf': udf21[0], 'nda': nda21[0]}
        for a, name21 in names_2021.items():
            mn = _norm(name21)
            best_i, best_score = None, 0
            for i, bc in enumerate(booth_cands):
                bn = _norm(bc)
                score = 0
                for lng in range(4, min(len(mn), len(bn)) + 1):
                    for s in range(len(mn) - lng + 1):
                        if mn[s:s+lng] in bn:
                            score = max(score, lng)
                if score > best_score:
                    best_score, best_i = score, i
            if best_i is not None and best_score >= 4:
                booth_ali_idx[a] = best_i

    def _booth_alliance_total(row):
        votes = row.get("votes", [])
        return sum(
            votes[i] if i < len(votes) else 0
            for i in booth_ali_idx.values()
        )

    total_2021_all = sum(_booth_alliance_total(b) for b in booths)

    def _2021_shares_at_pct(pct):
        """Return {ldf,udf,nda} vote shares in 2021 for the first pct*alliance votes."""
        if total_2021_all <= 0:
            return {"ldf": 0.0, "udf": 0.0, "nda": 0.0}
        target  = pct * total_2021_all
        running = 0
        cutoff  = set()
        for bn in main_nos:
            running += sum(_booth_alliance_total(b) for b in booths if b["main"] == bn)
            cutoff.add(bn)
            if running >= target:
                break
        early = [b for b in booths if b["main"] in cutoff]
        vals  = {a: sum(b["votes"][i] if i < len(b.get("votes", [])) else 0
                        for b in early)
                 for a, i in booth_ali_idx.items()}
        total = sum(vals.values())
        if total == 0:
            return {"ldf": 0.0, "udf": 0.0, "nda": 0.0}
        return {a: round(vals.get(a, 0) / total * 100, 1)
                for a in ("ldf", "udf", "nda")}

    def _safe_share(v, total):
        return round(v / total * 100, 1) if total > 0 else 0.0

    enriched_rounds = []
    for rr in rounds:
        pct   = min(rr["round"] / tot_rounds, 1.0)
        cumul = rr.get("cumulative", [])

        v26 = {a: (cumul[alliance_idx[a]] if alliance_idx.get(a) is not None
                   and alliance_idx[a] < len(cumul) else 0)
               for a in ("ldf", "udf", "nda")}
        total_26 = sum(c for c in cumul if isinstance(c, (int, float)))

        s26  = {a: _safe_share(v26[a], total_26) for a in ("ldf", "udf", "nda")}
        s21  = _2021_shares_at_pct(pct)
        delta = {a: round(s26[a] - s21[a], 1) for a in ("ldf", "udf", "nda")}

        enriched_rounds.append({
            **rr,
            "pct":          round(pct * 100, 1),
            "alliance_v26": v26,
            "share_2026":   s26,
            "share_2021":   s21,
            "delta":        delta,
        })

    return jsonify({**result, "rounds": enriched_rounds, "tot_rounds": tot_rounds,
                    "candidate_alliances": candidate_alliances,
                    "alliance_idx": alliance_idx})


if __name__ == "__main__":
    try:
        import flask
    except ImportError:
        print("Installing Flask…")
        os.system(f"{sys.executable} -m pip install flask --quiet")
    print("\n  Kerala Election Live Predictor")
    print("   Open -> http://localhost:5000\n")
    app.run(debug=True, port=5000)
