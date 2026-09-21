#!/usr/bin/env python3
"""
CLAUDE_B track — build_dataset.py
Builds RAW_DATASET (CSV + JSON) from values transcribed verbatim from fetched public pages
on 2026-09-22 (UTC). No value below was produced from memory; each row carries provenance.
Feature fields (bpm, key, mode, duration, energy, ...) are null except where a feature page
was actually read (only G003 "Shape of You"), because per-song feature collection was halted
by operator instruction on 2026-09-22 before the parallel collectors ran.
"""
import csv, json, os
from datetime import date

OBS = "2026-09-22"
OUT = os.path.join(os.path.dirname(__file__), "..", "data")

SRC = {
 "W1": {"id":"W1","name":"Wikipedia – List of most-viewed YouTube videos","url":"https://en.wikipedia.org/wiki/List_of_most-viewed_YouTube_videos","as_of":"2026-08-30","observed":OBS,"note":"views rounded to nearest 10M; 30-row table"},
 "K4": {"id":"K4","name":"kworb.net – Most viewed music videos of all time","url":"https://kworb.net/youtube/topvideos.html","as_of":None,"observed":OBS,"note":"exact view counts; page prints no update date; 'Yesterday' = views gained previous day (undated)"},
 "S2": {"id":"S2","name":"Wikipedia – List of Spotify streaming records (most-streamed songs)","url":"https://en.wikipedia.org/wiki/List_of_Spotify_streaming_records","as_of":"2026-09-13","observed":OBS,"note":"streams in billions, 3 dp"},
 "B3": {"id":"B3","name":"Wikipedia – Billboard Hot 100 chart achievements (most total weeks at #1)","url":"https://en.wikipedia.org/wiki/List_of_Billboard_Hot_100_chart_achievements_and_milestones","as_of":"2026-01-03 (chart dated; caveat: one 2026 entry present)","observed":OBS,"note":"weeks at #1"},
 "WI": {"id":"WI","name":"Wikipedia – List of most-viewed Indian YouTube videos","url":"https://en.wikipedia.org/wiki/List_of_most-viewed_Indian_YouTube_videos","as_of":"2026-02-18","observed":OBS,"note":"exact counts on page, transcribed as billions (3 dp); film status inferred from 'from <Film>' annotation"},
 "KI": {"id":"KI","name":"kworb.net – Most viewed music videos by Indian artists","url":"https://kworb.net/youtube/topvideos_indian.html","as_of":None,"observed":OBS,"note":"no update date printed"},
 "SI": {"id":"SI","name":"kworb.net – Spotify India daily chart totals","url":"https://kworb.net/spotify/country/in_daily_totals.html","as_of":"2026-08-26","observed":OBS,"note":"'Total' = streams accumulated on days the song was in the India daily top-200 since 2019-02-27 — NOT lifetime streams; Days = chart days; Pk = peak position; PkStreams = best single-day streams"},
 "BI": {"id":"BI","name":"Wikipedia – India Songs (Billboard) number ones","url":"https://en.wikipedia.org/wiki/India_Songs","as_of":"2022 rows only","observed":OBS,"note":"chart launched Feb 2022; page lists 2022 number-ones only"},
 "TB": {"id":"TB","name":"Tunebat – Shape of You (Spotify-derived features)","url":"https://tunebat.com/Info/Shape-of-You-Ed-Sheeran/7qiZfU4dY1lWllzX7mPBI3","as_of":None,"observed":OBS,"note":"secondary estimate (Spotify audio features)"},
 "SB": {"id":"SB","name":"SongBPM – Shape of You","url":"https://songbpm.com/@ed-sheeran/shape-of-you","as_of":None,"observed":OBS,"note":"secondary estimate; states 'Song data provided by Spotify'"},
 "GB": {"id":"GB","name":"GetSongBPM – Shape of You","url":"https://getsongbpm.com/song/shape-of-you/x6gjyP","as_of":None,"observed":OBS,"note":"secondary estimate; sources MusicBrainz/Last.fm/Spotify"},
}

# ---------- GLOBAL cohort (music-only rows; values as read) ----------
# (id, title, artist_as_listed, yt_views_W1_bn, yt_views_K4_exact, k4_yesterday, upload_date_W1, sp_streams_S2_bn, sp_release_S2, hot100_weeks_B3, flags)
G = [
("G001","Despacito","Luis Fonsi ft. Daddy Yankee",9.11,9126588087,1013280,"2017-01-12",None,None,16,""),
("G002","See You Again","Wiz Khalifa ft. Charlie Puth",7.08,7091120482,977840,"2015-04-06",None,None,None,""),
("G003","Shape of You","Ed Sheeran",6.79,6807738194,996907,"2017-01-30",5.095,"2017-01-06",None,""),
("G004","Axel F","Crazy Frog",6.14,6185715587,2630802,"2009-06-16",None,None,None,"borderline_novelty"),
("G005","Gangnam Style","Psy",6.05,6066050604,1259847,"2012-07-15",None,None,None,""),
("G006","Uptown Funk","Mark Ronson ft. Bruno Mars",5.89,5903516076,760402,"2014-11-19",None,None,14,""),
("G007","Dame Tu Cosita","El Chombo feat. Cutty Ranks",5.60,5633751011,1994799,"2018-04-05",None,None,None,"borderline_novelty"),
("G008","Waka Waka (This Time for Africa)","Shakira",4.73,4761296476,1478977,"2010-06-04",None,None,None,""),
("G009","Counting Stars","OneRepublic",4.40,4512287231,928060,"2013-05-31",3.642,"2013-06-14",None,""),
("G010","Sugar","Maroon 5",4.37,4428285623,510964,"2015-01-14",None,None,None,""),
("G011","Roar","Katy Perry",4.30,4375219775,650720,"2013-09-05",None,None,None,""),
("G012","Dark Horse","Katy Perry ft. Juicy J",4.15,4241029862,711422,"2014-02-20",None,None,None,""),
("G013","Perfect","Ed Sheeran",4.14,4227599564,830710,"2017-11-09",4.108,"2017-03-03",None,""),
("G014","Sorry","Justin Bieber",4.09,4155388310,537006,"2015-10-22",None,None,None,""),
("G015","Let Her Go","Passenger",4.04,4143467300,757751,"2012-07-25",None,None,None,""),
("G016","Girls Like You","Maroon 5 ft. Cardi B",4.00,4081780443,677948,"2018-05-31",None,None,None,""),
("G017","Thinking Out Loud","Ed Sheeran",None,4044000493,541087,None,None,None,None,""),
("G018","Faded","Alan Walker",None,4032829375,718563,None,None,None,None,""),
("G019","Lean On","Major Lazer & DJ Snake feat. MØ",None,3969075180,492165,None,None,None,None,""),
("G020","Bailando","Enrique Iglesias ft. Descemer Bueno, Gente De Zona",None,3888716418,524851,None,None,None,None,""),
("G021","Blank Space","Taylor Swift",None,3855685525,554285,None,None,None,None,""),
("G022","Baby","Justin Bieber ft. Ludacris",None,3753649230,868476,"2010-02-19",None,None,None,"upload_date_from_W1_progression_table"),
("G023","Let It Go","Idina Menzel",None,3730983278,557768,None,None,None,None,"film_soundtrack"),
("G024","Shake It Off","Taylor Swift",None,3729598219,470402,None,None,None,None,""),
("G025","Mi Gente","J Balvin, Willy William",None,3709333381,604296,None,None,None,None,""),
("G026","We Don't Talk Anymore","Charlie Puth feat. Selena Gomez",None,3603042834,743124,None,None,None,None,""),
("G027","Closer","The Chainsmokers ft. Halsey",None,3459967793,670239,None,3.877,"2016-07-29",None,"K4_row_is_lyric_video"),
("G028","New Rules","Dua Lipa",None,3329312681,511365,None,None,None,None,""),
("G029","The Lazy Song","Bruno Mars",None,3297190489,857806,None,None,None,None,""),
("G030","Hello","Adele",None,3279315500,216909,None,None,None,None,""),
("G031","Stressed Out","twenty one pilots",None,3264883079,560757,None,None,None,None,""),
("G032","Chantaje","Shakira ft. Maluma",None,3218755741,470377,None,None,None,None,""),
("G033","Rockabye","Clean Bandit feat. Sean Paul & Anne-Marie",None,3218234087,307158,None,None,None,None,""),
("G034","Con Calma","Daddy Yankee & Snow",None,3217548577,552574,None,None,None,None,""),
("G035","Love The Way You Lie","Eminem ft. Rihanna",None,3195160694,752214,None,None,None,None,""),
("G036","Calma (Remix)","Pedro Capó, Farruko",None,3183146695,457019,None,None,None,None,""),
("G037","Sunflower","Post Malone, Swae Lee",None,3135691918,2254050,None,4.456,"2018-10-18",None,""),
("G038","Work from Home","Fifth Harmony ft. Ty Dolla $ign",None,3115587644,423962,None,None,None,None,""),
("G039","Blinding Lights","The Weeknd",None,None,None,None,5.588,"2019-11-29",None,""),
("G040","Sweater Weather","The Neighbourhood",None,None,None,None,4.874,"2012-12-03",None,""),
("G041","Starboy","The Weeknd and Daft Punk",None,None,None,None,4.753,"2016-09-21",None,""),
("G042","As It Was","Harry Styles",None,None,None,None,4.622,"2022-04-01",15,""),
("G043","One Dance","Drake, Wizkid, Kyla",None,None,None,None,4.463,"2016-04-05",None,""),
("G044","Someone You Loved","Lewis Capaldi",None,None,None,None,4.435,"2018-11-08",None,""),
("G045","Stay","The Kid Laroi and Justin Bieber",None,None,None,None,4.073,"2021-07-27",None,""),
("G046","I Wanna Be Yours","Arctic Monkeys",None,None,None,None,3.995,"2013-09-09",None,""),
("G047","Die With A Smile","Lady Gaga and Bruno Mars",None,None,None,None,3.980,"2024-08-16",None,""),
("G048","Birds of a Feather","Billie Eilish",None,None,None,None,3.977,"2024-05-17",None,""),
("G049","Yellow","Coldplay",None,None,None,None,3.973,"2000-06-26",None,""),
("G050","Believer","Imagine Dragons",None,None,None,None,3.959,"2017-02-01",None,""),
("G051","The Night We Met","Lord Huron",None,None,None,None,3.927,"2015-04-07",None,""),
("G052","Heat Waves","Glass Animals",None,None,None,None,3.927,"2020-06-29",None,""),
("G053","Riptide","Vance Joy",None,None,None,None,3.906,"2013-05-21",None,""),
("G054","Lovely","Billie Eilish and Khalid",None,None,None,None,3.875,"2018-04-19",None,""),
("G055","Something Just Like This","The Chainsmokers and Coldplay",None,None,None,None,3.771,"2017-02-22",None,""),
("G056","Every Breath You Take","The Police",None,None,None,None,3.750,"1983-05-20",None,"catalog_pre2010"),
("G057","Iris","The Goo Goo Dolls",None,None,None,None,3.700,"1998-04-01",None,"catalog_pre2010"),
("G058","Another Love","Tom Odell",None,None,None,None,3.693,"2012-10-15",None,""),
("G059","Say You Won't Let Go","James Arthur",None,None,None,None,3.693,"2016-09-09",None,""),
("G060","Take Me To Church","Hozier",None,None,None,None,3.586,"2013-09-13",None,""),
("G061","Photograph","Ed Sheeran",None,None,None,None,3.549,"2014-06-20",None,""),
("G062","Viva La Vida","Coldplay",None,None,None,None,3.516,"2008-05-25",None,"catalog_pre2010"),
("G063","Dance Monkey","Tones And I",None,None,None,None,3.510,"2019-05-10",None,""),
("G064","Can't Hold Us","Macklemore & Ryan Lewis feat. Ray Dalton",None,None,None,None,3.501,"2011-08-16",None,""),
("G065","Locked Out Of Heaven","Bruno Mars",None,None,None,None,3.492,"2012-10-01",None,""),
("G066","Cruel Summer","Taylor Swift",None,None,None,None,3.483,"2019-08-23",None,""),
("G067","Just the Way You Are","Bruno Mars",None,None,None,None,3.472,"2010-07-20",None,""),
("G068","Mr. Brightside","The Killers",None,None,None,None,3.466,"2003-09-29",None,"catalog_pre2010"),
("G069","Rockstar","Post Malone and 21 Savage",None,None,None,None,3.452,"2017-09-15",None,""),
("G070","Señorita","Shawn Mendes and Camila Cabello",None,None,None,None,3.418,"2019-06-21",None,""),
("G071","Die For You","The Weeknd",None,None,None,None,3.415,"2016-11-25",None,""),
("G072","Watermelon Sugar","Harry Styles",None,None,None,None,3.395,"2019-11-16",None,""),
("G073","That's What I Like","Bruno Mars",None,None,None,None,3.391,"2017-01-30",None,""),
# Billboard-longevity-only rows (chart weeks observed; no view/stream value read)
("G074","All I Want for Christmas Is You","Mariah Carey",None,None,None,None,None,None,22,"B3_only; chart years 2019-2026; original release 1994 (not read on page)"),
("G075","Choosin' Texas","Ella Langley",None,None,None,None,None,None,21,"B3_only; 2026"),
("G076","Old Town Road","Lil Nas X feat. Billy Ray Cyrus",None,None,None,None,None,None,19,"B3_only; 2019"),
("G077","A Bar Song (Tipsy)","Shaboozey",None,None,None,None,None,None,19,"B3_only; 2024"),
("G078","One Sweet Day","Mariah Carey and Boyz II Men",None,None,None,None,None,None,16,"B3_only; 1995-1996"),
("G079","Last Night","Morgan Wallen",None,None,None,None,None,None,16,"B3_only; 2023"),
("G080","I Will Always Love You","Whitney Houston",None,None,None,None,None,None,14,"B3_only; 1992-1993"),
("G081","I'll Make Love to You","Boyz II Men",None,None,None,None,None,None,14,"B3_only; 1994"),
("G082","Macarena (Bayside Boys Mix)","Los del Río",None,None,None,None,None,None,14,"B3_only; 1996"),
("G083","Candle in the Wind 1997 / Something About the Way You Look Tonight","Elton John",None,None,None,None,None,None,14,"B3_only; 1997-1998"),
("G084","We Belong Together","Mariah Carey",None,None,None,None,None,None,14,"B3_only; 2005"),
("G085","I Gotta Feeling","The Black Eyed Peas",None,None,None,None,None,None,14,"B3_only; 2009"),
]

# ---------- HINDI / INDIAN cohort ----------
# YouTube rows: (id, title_as_listed, uploader_WI, language_WI, views_WI_bn, upload_date_WI, film_status(WI annotation), views_KI_exact, ki_yesterday, singer_from_KI_title)
HY = [
("H001","Lehanga","Geet MP3","Punjabi",1.835,"2019-08-13","non-film(inferred)",1870804491,265995,"Jass Manak"),
("H002","52 Gaj Ka Daman","Desi Records","Haryanvi",1.752,"2020-10-02","non-film(inferred)",1786986265,152662,"Pranjal Dahiya / Aman Jaji / Renuka Panwar"),
("H003","Zaroori Tha","The Folk & Soul Studio","Hindi",1.730,"2014-06-09","non-film(inferred)",1769377733,334446,"Rahat Fateh Ali Khan"),
("H004","Rowdy Baby (Maari 2)","Wunderbar Films","Tamil",1.729,"2019-01-02","film",1757984929,147174,None),
("H005","Vaaste","T-Series","Hindi",1.717,"2019-04-06","non-film(inferred)",1756960664,264633,"Dhvani Bhanushali, Tanishk Bagchi, Nikhil D'Souza"),
("H006","Laung Laachi (Title Track)","T-Series Apna Punjab","Punjabi",1.631,"2018-02-21","film",1651662867,149000,"Mannat Noor"),
("H007","Dilbar (Lyrical) (Satyameva Jayate)","T-Series","Hindi",1.537,"2018-07-09","film",1594310296,382277,None),
("H008","Lut Gaye","T-Series","Hindi",1.521,"2021-02-17","non-film(inferred)",1554044193,231357,"Jubin Nautiyal, Tanishk Bagchi"),
("H009","Bum Bum Bole (Taare Zameen Par)","T-Series","Hindi",1.453,"2011-05-25","film",1569562984,718197,"Shaan"),
("H010","Tujh Mein Rab Dikhta Hai (Rab Ne Bana Di Jodi)","Yash Raj Films","Hindi",1.423,"2012-01-19","film",1518900920,583768,None),
("H011","Mile Ho Tum (Reprise) (Fever)","Zee Music Company","Hindi",1.390,"2016-07-27","film",1404590011,87641,"Neha Kakkar, Tony Kakkar"),
("H012","Cham Cham (Baaghi)","T-Series","Hindi",1.392,"2016-05-06","film",1439587192,298615,None),
("H013","Bom Diggy Diggy (Sonu Ke Titu Ki Sweety)","T-Series","Hindi",1.376,"2018-02-08","film",1443437698,461365,"Zack Knight, Jasmin Walia"),
("H014","High Rated Gabru","T-Series","Punjabi",1.298,"2017-07-04","non-film(inferred)",1321615858,149738,"Guru Randhawa"),
("H015","Aankh Maarey (Lyrical) (Simmba)","T-Series","Hindi",1.279,"2018-12-11","film",1290074083,70170,None),
("H016","Dil Laga Liya (Dil Hai Tumhaara)","Tips Industries","Hindi",1.264,"2009-12-09","film",1298750085,331389,None),
("H017","Khairiyat (Chhichhore)","T-Series","Hindi",1.231,"2019-09-26","film",1283641722,309406,None),
("H018","Tum Hi Aana (Marjaavaan)","T-Series","Hindi",1.237,"2019-10-15","film",1358018037,951068,None),
("H019","Jhoome Jo Pathaan (Pathaan)","Yash Raj Films","Hindi",1.229,"2022-12-22","film",1275311935,239367,None),
("H020","Humnava Mere","T-Series","Hindi",1.230,"2018-05-23","non-film(inferred)",1320602693,601976,"Jubin Nautiyal"),
("H021","Abhi Toh Party Shuru Hui Hai (Khoobsurat)","T-Series","Hindi",1.215,"2014-11-11","film",1307714573,611110,None),
("H022","Phir Bhi Tumko Chaahunga (Half Girlfriend)","Zee Music Company","Hindi",1.209,"2017-07-06","film",1260552049,294238,"Arijit Singh"),
("H023","Daru Badnaam","VIP Records","Punjabi",1.199,"2016-12-25","non-film(inferred)",1229812305,157382,"Kamal Kahlon & Param Singh"),
("H024","Filhall","Desi Melodies","Hindi/Punjabi",1.187,"2019-11-09","non-film(inferred)",1195313221,55589,"B Praak (ft. Akshay Kumar, Nupur Sanon in video)"),
("H025","Chatak Matak","VATS RECORDS","Haryanvi",1.152,"2020-12-20","non-film(inferred)",1184938840,139228,"Sapna Choudhary (performer in title)"),
("H026","8 Parche","Ishtar Punjabi","Punjabi",1.153,"2019-09-12","non-film(inferred)",1254521626,464124,"Baani Sandhu, Gur Sidhu"),
("H027","Lahore","T-Series","Punjabi",1.152,"2017-12-14","non-film(inferred)",1171916512,107330,"Guru Randhawa"),
("H028","Kala Chashma (Baar Baar Dekho)","Zee Music Company","Hindi/Punjabi",1.133,"2016-07-27","film",1200127095,319213,None),
("H029","Galti Se Mistake (Jagga Jasoos)","T-Series","Hindi",1.109,"2017-06-09","film",1183909769,290660,None),
("H030","Jaha Tum Rahoge (Maheruh)","Zee Music Company","Hindi",1.094,"2017-11-02","film",1141798253,161589,None),
("H031","Leja Re","T-Series","Hindi",1.056,"2018-11-24","non-film(inferred)",1083355182,94491,"Dhvani Bhanushali, Tanishk Bagchi"),
("H032","Genda Phool","Sony Music India","Hindi/Bengali",1.051,"2020-03-26","non-film(inferred)",1081470439,138543,"Badshah"),
("H033","Aankh Maarey (Simmba)","T-Series","Hindi",1.049,"2018-12-06","film",1079283510,122826,None),
("H034","O Saki Saki (Batla House)","T-Series","Hindi",1.048,"2019-08-29","film",1131970402,485124,None),
("H035","Hello Koun","Riddhi Music World","Bhojpuri",1.037,"2019-12-10","non-film(inferred)",None,None,None),
("H036","Prem Ratan Dhan Payo (Prem Ratan Dhan Payo)","T-Series","Hindi",1.025,"2015-12-01","film",1060255714,186803,None),
("H037","Titliaan","DM - Desi Melodies","Punjabi",1.006,"2020-11-09","non-film(inferred)",None,None,None),
("H038","Aaj Ki Raat (Stree 2)","Saregama Music","Hindi",1.012,"2024-07-24","film",1073298154,279400,None),
("H039","Bole Chudiyan (K3G)",None,None,None,None,"film(inferred from title)",1063744424,444886,None),
("H040","Chittiyaan Kalaiyaan (Roy)",None,None,None,None,"film(inferred from title)",1061633025,462058,None),
]
# Spotify India rows: (id, artist_field, title_as_listed, days, t10, pk, pk_x, pkstreams, total, film_tag_from_title)
HS = [
("H041","Alka Yagnik","Agar Tum Saath Ho (From \"Tamasha\")",2520,131,4,None,730083,653520827,"film"),
("H042","Arijit Singh","Tujhe Kitna Chahne Lage (From \"Kabir Singh\")",2644,416,2,50,621964,609868808,"film"),
("H043","Sachin-Jigar","Apna Bana Le",1029,268,1,14,1446847,558530245,None),
("H044","Anuv Jain","Jo Tum Mere Ho",747,381,1,105,1697410,527793639,None),
("H045","Faheem Abdullah","Ishq",824,514,2,14,1106120,519495029,None),
("H046","Gajendra Verma","Mann Mera",1495,115,5,None,741874,517287162,None),
("H047","Vishal Mishra","Kaise Hua (From \"Kabir Singh\")",2630,34,4,None,467802,516408938,"film"),
("H048","Pritam","Tum Se Hi",2343,3,7,None,584353,504626295,None),
("H049","King","Maan Meri Jaan",863,275,1,123,2032986,483747313,None),
("H050","Arijit Singh","Humdard (From \"Ek Villain\")",2239,None,13,None,620369,482243234,"film"),
("H051","Pritam","Kesariya",1154,289,1,44,1213960,480100067,None),
("H052","AP Dhillon","Excuses",1470,304,1,101,1309583,476757167,None),
("H053","Pritam","Shayad",2224,404,1,93,404167,475943252,None),
("H054","Aditya Rikhari","Sahiba",421,375,1,124,1961280,463736702,None),
("H055","Jasleen Royal","Ranjha (From \"Shershaah\")",1481,246,1,6,1084063,447398550,"film"),
("H056","Sachet-Parampara","Raanjhan (From \"Do Patti\")",676,296,1,42,1467166,446470310,"film"),
("H057","Anuv Jain","Husn",1000,231,1,23,1363695,442611145,None),
("H058","Kushagra","Finding Her",540,488,1,54,1351987,442351861,None),
("H059","Arijit Singh","Satranga (From \"ANIMAL\")",894,260,2,43,1731421,436414693,"film"),
("H060","Anuv Jain","Baarishein",1932,None,15,None,504597,436331649,None),
("H061","Sachin-Jigar","Saibo",2131,None,18,None,464953,423972644,None),
("H062","Shubh","Cheques",1029,172,1,27,1410911,422610766,None),
("H063","Shubh","One Love",1097,168,3,36,1033472,409440499,None),
("H064","King","Tu Aake Dekhle",1431,407,3,15,886224,404564161,None),
("H065","Ram Sampath","Sajni (From \"Laapataa Ladies\")",835,267,1,59,1417932,397427230,"film"),
("H066","Tanishk Bagchi","Raataan Lambiyan (From \"Shershaah\")",1166,294,1,141,1235566,392749979,"film"),
("H067","Jasleen Royal","Heeriye",783,182,1,27,2241774,391887513,None),
("H068","Atif Aslam","Tera Hone Laga Hoon",1927,None,20,None,441621,390632280,None),
("H069","Sachet Tandon","Mere Sohneya (From \"Kabir Singh\")",2312,83,4,None,445571,381459758,"film"),
("H070","Sachet Tandon","Malang Sajna",1156,132,4,None,744978,368190456,None),
("H071","Atif Aslam","Dil Diyan Gallan",2357,None,20,None,419943,365551514,None),
("H072","Anirudh Ravichander","Chaleya",657,251,1,43,2295124,363914136,None),
("H073","Vishal Mishra","Pehle Bhi Main",646,215,1,124,2091461,361968556,None),
("H074","Karan Aujla","Softly",994,82,4,None,826800,359253336,None),
("H075","Pritam","Kabira",2397,None,30,None,399527,354517727,None),
("H076","Pritam","Ye Tune Kya Kiya",930,31,8,None,615073,340350923,None),
("H077","Jawad Ahmad","Samjhawan",1793,113,2,2,901735,336840988,None),
]
# Billboard India Songs 2022 #1s: (id, song, artist, weeks_at_1, date_reached)
HB = [
("H078","Srivalli","Sid Sriram",9,"2022-02-19"),
("H079","Mehbooba","Ananya Bhat",6,"2022-05-07"),
("H080","Komuram Bheemudho","Kaala Bhairava",2,"2022-05-21"),
("H081","The Last Ride","Sidhu Moose Wala",14,"2022-06-11"),
("H082","295","Sidhu Moose Wala",18,"2022-06-18"),
("H083","Ra Ra Rakkamma","Nakash Aziz & Sunidhi Chauhan",1,"2022-08-27"),
]
# Cross-list: Kesariya also #1 India Songs 2022 for 3 weeks (BI) — attached to H051.
# Shree Hanuman Chalisa excluded (devotional recitation) from song cohorts; kept in exclusions log.

FEATURE_FIELDS = ["bpm","bpm_alt","perceived_pulse_note","tempo_change","key","mode","emotion","energy","groove","meter",
 "song_duration_sec","intro_length_sec","first_vocal_sec","first_hook_sec","chorus_arrival_sec","hook_repetitions",
 "structure","melodic_contour","vocal_range_measured","tessitura","climax_placement","arrangement_production_era",
 "feature_provenance_urls","feature_method","feature_confidence","feature_kind"]

def blank_features():
    return {k: None for k in FEATURE_FIELDS}

def days_since(d):
    y,m,dd = map(int, d.split("-"))
    return (date(2026,9,22) - date(y,m,dd)).days

rows = []
for (i,t,a,w1,k4,ky,up,s2,rel,b3,fl) in G:
    r = {"id":i,"cohort":"GLOBAL_SUCCESS","title":t,"artist_as_listed":a,"market":"global","language":None,
         "film_status":"film_soundtrack" if "film_soundtrack" in fl else "non-film",
         "success_yt_views_W1_bn":w1,"success_yt_views_K4_exact":k4,"success_yt_yesterday_K4":ky,
         "official_upload_date":up,"upload_age_days_at_obs":days_since(up) if up else None,
         "success_spotify_streams_S2_bn":s2,"release_date_S2":rel,"success_hot100_weeks_at_1_B3":b3,
         "success_sources":",".join([s for s,v in (("W1",w1),("K4",k4),("S2",s2),("B3",b3)) if v is not None]),
         "era_year": int((up or rel or "0000")[:4]) if (up or rel) else None,
         "flags":fl}
    r.update(blank_features())
    rows.append(r)
for (i,t,upl,lang,wv,up,fs,kv,ky,singer) in HY:
    r = {"id":i,"cohort":"HINDI_INDIAN_SUCCESS","title":t,"artist_as_listed":singer,"market":"india","language":lang,
         "film_status":fs,"uploader":upl,
         "success_yt_views_WI_bn":wv,"success_yt_views_KI_exact":kv,"success_yt_yesterday_KI":ky,
         "official_upload_date":up,"upload_age_days_at_obs":days_since(up) if up else None,
         "success_sources":",".join([s for s,v in (("WI",wv),("KI",kv)) if v is not None]),
         "era_year": int(up[:4]) if up else None,"flags":""}
    r.update(blank_features()); rows.append(r)
for (i,art,t,days,t10,pk,pkx,pks,tot,film) in HS:
    r = {"id":i,"cohort":"HINDI_INDIAN_SUCCESS","title":t,"artist_as_listed":art,"market":"india","language":None,
         "film_status":film,"success_spotify_in_chart_days_SI":days,"success_spotify_in_top10_days_SI":t10,
         "success_spotify_in_peak_pos_SI":pk,"success_spotify_in_days_at_peak_SI":pkx,
         "success_spotify_in_peak_day_streams_SI":pks,"success_spotify_in_chart_total_streams_SI":tot,
         "success_india_songs_weeks_at_1_BI": 3 if i=="H051" else None,
         "success_sources":"SI"+(",BI" if i=="H051" else ""),"era_year":None,"flags":"chart-day totals only (since 2019-02-27)"}
    r.update(blank_features()); rows.append(r)
for (i,t,a,wk,d) in HB:
    r = {"id":i,"cohort":"HINDI_INDIAN_SUCCESS","title":t,"artist_as_listed":a,"market":"india","language":None,
         "film_status":None,"success_india_songs_weeks_at_1_BI":wk,"success_india_songs_date_reached_1_BI":d,
         "success_sources":"BI","era_year":2022,"flags":"BI_only"}
    r.update(blank_features()); rows.append(r)

# The single row with actually-read feature values (three feature pages fetched by the lead analyst)
for r in rows:
    if r["id"]=="G003":
        r.update({"bpm":96,"bpm_alt":"192 (SongBPM: 'can also be used double-time')","key":"C#/Db","mode":"minor",
                  "energy":"65 (Tunebat) / 66 (GetSongBPM) / 'high energy' (SongBPM)",
                  "emotion":"happiness 93 (Tunebat valence-type score)","groove":"danceability 83 (Tunebat & GetSongBPM)",
                  "meter":"4/4 (SongBPM, GetSongBPM)","song_duration_sec":234,
                  "arrangement_production_era":"loudness -3 dB, acousticness 58 (Tunebat); release 2017-03-03 (Tunebat, album ÷ Deluxe)",
                  "feature_provenance_urls":"TB;SB;GB","feature_method":"Spotify-derived audio features as republished by Tunebat/SongBPM/GetSongBPM; three-site agreement on BPM=96, two-site agreement on key C# minor; duration 3:54 (TB,SB) vs 3:53 (GB)",
                  "feature_confidence":"medium (secondary, cross-checked 3 sites)","feature_kind":"secondary_estimate"})

# exclusions log
exclusions = [
 {"title":"Shree Hanuman Chalisa","reason":"devotional recitation, not a commercial song; appears in W1, WI, KI, SI, BI","sources":"W1,WI,KI,SI,BI"},
 {"title":"Sankat Mochan Hanuman Ashtak","reason":"devotional","sources":"KI"},
 {"title":"Gummibär – The Gummy Bear Song","reason":"kids/novelty","sources":"K4"},
 {"title":"Baby Shark Dance / Cocomelon / LooLoo / ChuChu / Miroshka / Jingle Toons / Kiddiestv rows","reason":"kids content","sources":"W1,WI"},
 {"title":"Facebook ad; Temu ad; Masha and the Bear","reason":"ads / animation episodes","sources":"W1"},
 {"title":"Starboy, Perfect (kworb Spotify India), Pink Venom (India Songs)","reason":"non-Indian repertoire in Indian source; kept in GLOBAL cohort where applicable","sources":"SI,BI"},
 {"title":"kworb Spotify India daily chart (in_daily.html) top-40","reason":"single-day snapshot (2026-08-26) — recorded in provenance, not used as a cohort because it is a point-in-time chart, not a longevity measure","sources":"kworb in_daily"},
]

os.makedirs(OUT, exist_ok=True)
first=["id","cohort","title","artist_as_listed"]
cols = first + sorted({k for r in rows for k in r} - set(first))
with open(os.path.join(OUT,"RAW_DATASET.csv"),"w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for r in rows: w.writerow({k:("" if r.get(k) is None else r.get(k)) for k in cols})
json.dump({"track":"CLAUDE_B","version":"FROZEN_V01","observed":OBS,"unit_of_record":"one recording = one official upload/stream entity as listed by source",
           "sources":SRC,"rows":rows,"exclusions":exclusions,
           "unchained_nitin_own_data":{"status":"future cohort","rows":[],"note":"no observations exist; nothing invented"}},
          open(os.path.join(OUT,"RAW_DATASET.json"),"w",encoding="utf-8"), indent=1, ensure_ascii=False)
with open(os.path.join(OUT,"SOURCES_PROVENANCE.csv"),"w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["id","name","url","as_of","observed","note"]); w.writeheader()
    for s in SRC.values(): w.writerow(s)
print("rows:", len(rows), "cols:", len(cols))
