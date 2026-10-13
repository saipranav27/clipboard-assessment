SITE = """Bellhaven of Maplewood|210 Orchard Lane|Maplewood|OH|44280|AL
Bellhaven of New Carlisle|875 Elm Street|New Carlisle|OH|45344|SNF
Bellhaven of Wooster|2301 Cleveland Road|Wooster|OH|44691|SNF
Bellhaven Terrace of Akron|55 Ridgewood Avenue|Akron|OH|44313|AL
Bellhaven of Saline|980 W Michigan Ave|Saline|MI|48176|SNF
Bellhaven of Goshen|1610 College Ave|Goshen|IN|46526|AL
Bellhaven of Meadville|341 Chestnut St|Meadville|PA|16335|SNF
Bellhaven of Defiance|700 Carpenter Rd|Defiance|OH|43512|SNF
Bellhaven Woods of Toledo|4850 NW Sylvania Ave|Toledo|OH|43623|MS
Bellhaven of Marion|199 Barks Rd W|Marion|OH|43302|SNF
Bellhaven of Kalamazoo|3222 Gull Rd|Kalamazoo|MI|49048|SNF
Bellhaven Court of Altoona|1125 Logan Blvd|Altoona|PA|16602|AL
Bellhaven Rehabilitation & Nursing of Grove City|3985 Broadway|Grove City|OH|43123|SNF
Bellhaven at Sycamore Ridge|7420 Sycamore Ridge Dr|Miamisburg|OH|45342|AL
The Arbors at Bellhaven - Dayton|2210 Salem Ave|Dayton|OH|45406|MS
Bellhaven Healthcare Centre of Ashland|1631 Claremont Ave|Ashland|OH|44805|SNF
Bellhaven of Port Clinton|1420 Harbor Point Dr|Port Clinton|OH|43452|SNF
Bellhaven Shores of Erie|4930 W Lake Rd|Erie|PA|16505|AL,MS
Bellhaven of Kettering|3313 Wilmington Pike|Kettering|OH|45429|SNF
Bellhaven Gardens of Monroe|750 Stewart Rd|Monroe|MI|48162|AL
Bellhaven of Tiffin|45 St Lawrence Dr|Tiffin|OH|44883|SNF
Bellhaven of Marietta|805 Colegate Dr|Marietta|OH|45750|SNF
Bellhaven Crossings of Lima|3115 N Cole St|Lima|OH|45801|AL
Bellhaven of Zanesville|2680 Maple Ave|Zanesville|OH|43701|SNF
Bellhaven of Chagrin Falls|150 River St|Chagrin Falls|OH|44022|AL
Bellhaven Willow Creek|8060 Willow Creek Ln|Portage|MI|49024|MS
Bellhaven of Ashtabula|3156 W Prospect Rd|Ashtabula|OH|44004|SNF
Bellhaven of Owosso|1120 W Main St|Owosso|MI|48867|AL
Bellhaven of Portsmouth|2222 Gallia St|Portsmouth|OH|45662|SNF
Bellhaven of Batavia|2000 Hospital Dr|Batavia|OH|45103|SNF
Bellhaven at Union Square|118 Union Square Dr|New Albany|OH|43054|AL
Bellhaven of Carlisle|640 Walnut Bottom Rd|Carlisle|PA|17015|SNF
Bellhaven of Chesterton|1250 NW Franklin Street|Chesterton|IN|46304|SNF
Amberly Manor|4390 Darrow Rd|Hudson|OH|44236|AL
Bellhaven Meadows of Findlay|1800 N Blanchard St|Findlay|OH|45840|AL,MS"""
CARE = {"AL": "Assisted Living", "SNF": "Short-Term Rehabilitation & Nursing", "MS": "Memory Support"}
LOCATIONS = []
for l in SITE.splitlines():
    n, st, c, s, z, care = l.split("|")
    slug = n.lower().replace(" ", "-")
    LOCATIONS.append(dict(slug=slug, url="site/" + slug, name=n, street=st, city=c, state=s, zip=z, phone="",
                          care_offerings=[CARE[x] for x in care.split(",")], discovered_via=["directory"]))

ROWS = """0010KJFP601YNTZVDA|Arbors at Bellhaven Dayton|2210 Salem Ave|Dayton|OH|45406|BH|0|0
00116ETS45BL7DTQP7|Bellhaven Care Center of Alliance|1785 Freshley Ave|Alliance|OH|44601|BH|0|0
0011D2P3CWSHMF81C8|Bellhaven Court of Altoona|1125 Logan Boulevard|Altoona|PA|16602|BH|61000|0
001LGFPBJY4N9MB6KL|Bellhaven Crossings of Lima|3115 N Cole St|Lima|OH|45801|HV|47000|0
001U1750VLVJAGG1S5|Bellhaven Gardens of Monroe|750 Stewart Rd|Monroe|MI|48162|BH|0|0
001RJ0D7Z5MAZN5HX5|Bellhaven Health Care Center of Ashland|1631 Claremont Ave|Ashland|OH|44805|BH|0|0
001UKEFGADQ8YCZ4YM|Bellhaven Meadows of Findlay|1800 N Blanchard St|Findlay|OH|45840||22000|0
001TZCSTBZFM6K5BGN|Bellhaven Rehab and Nursing of Grove City|3985 Broadway|Grove City|OH|43123|BH|0|0
0015QAPLGS3FVYEEEM|Bellhaven Senior Living (Parent Account)||||||0|0
001CVBBCSDM7YHN220|Bellhaven Shores of Erie|4930 W Lake Rd|Erie|PA|16505|BH|0|0
0019Y4J61ZBG4R00CD|Bellhaven Terrace of Akron|55 Ridgewood Ave|Akron|OH|44313|BH|101000|9000
0014DHACE6WQU3RMM5|Bellhaven Woods of Toledo|4850 Northwest Sylvania Ave|Toledo|OH|43623|BH|54000|0
001NXP9X46CWEPSLSV|Bellhaven of Ashtabula|PO Box 517|Ashtabula|OH|44004|BH|0|0
0016PVXH4B25HWR7QE|Bellhaven of Coldwater|90 N Michigan Ave|Coldwater|MI|49036|BH|0|0
001R4PXTUD9R6FNN8V|Bellhaven of Defiance|700 Carpenter Road|Defiance|OH|43512|BH|66000|9500
001JQER1RMYKNRLNME|Bellhaven of Goshen|1610 College Avenue|Goshen|IN|46526|BH|121000|0
001NSHWKQD0YJLPQ20|Bellhaven of Kalamazoo|3222 Gull Road|Kalamazoo|MI|49048|BH|0|0
001L3LGR6W69J8DYYV|Bellhaven of Maplewood|210 Orchard Ln|Maplewood|OH|44280|BH|0|0
001A34WFSUYHCRBLFT|Bellhaven of Marietta|805 Colegate Drive|Marietta|OH|45750|CT|51250|3800
0015L38R1Z5947ZZP7|Bellhaven of Marion|199 Barks Road West|Marion|OH|43302|BH|87000|0
001KC1NG7EZDEKKA3T|Bellhaven of Meadville|341 Chestnut Street|Meadville|PA|16335|BH|87000|1000
001AQGPZ5G5VRES536|Bellhaven of New Carlisle|875 Elm St|New Carlisle|OH|45344|BH|156000|0
001EGU7BMJ942ZTRE6|Bellhaven of Owosso|1120 W Main St|Owosso|MI|48867|BH|0|0
001QU150PM4Z15UA71|Bellhaven of Owosso|1120 West Main Street|Owosso|MI|48867|BH|0|0
001UELXDAKFRKB8932|Bellhaven of Port Clinton|1420 Harbor Point Dr|Port Clinton|OH|43452|BH|0|0
001CF3LDWVRGL09P4F|Bellhaven of Portsmouth|2222 Gallia St|Portsmouth|OH|45626|BH|0|0
001MVVAPY6U5TVYRC4|Bellhaven of Saline|980 West Michigan Avenue|Saline|MI|48176|BH|0|0
001SXSF4ELF0Z2LGDM|Bellhaven of Sandusky|2715 Columbus Ave|Sandusky|OH|44870|BH|130000|5200
00191H7JR16471SZ34|Bellhaven of Sycamore Ridge|7420 Sycamore Ridge Dr|Miamisburg|OH|45342|BH|0|0
001U6RW32TY0WSXZZB|Bellhaven of Tiffin|45 St Lawrence Dr|Tiffin|OH|44883|CT|84000|12400
001W5G121A7SMRP58M|Bellhaven of Wooster|2301 Cleveland Rd|Wooster|OH|44691|BH|25000|0
001FWSQ30SFW6S7604|Cedar Trail Communities (Parent Account)||||||0|0
0011AB44D05WLA9HTX|Cedar Trail of Monroe|750 Stewart Road|Monroe|MI|48162|CT|0|0
001H1JMVZWP46D5VUF|Cedar Trail of Zanesville|2680 Maple Avenue|Zanesville|OH|43701|CT|0|0
0013NUZQHQUEZ8DXEG|Chesterton Senior Commons|1250 Northwest Franklin Street|Chesterton|IN|46304|BH|0|0
001FJZYHR7MLFMNPLL|Harborview Care Group (Parent Account)||||||0|0
001JD2MWRA74LTSN24|Harborview Nursing & Rehab of Port Clinton|1420 Harbor Point Drive|Port Clinton|OH|43452|HV|0|0
001BLYF02K97SZLZHH|Harborview Shores of Erie|4930 West Lake Road|Erie|PA|16505|HV|0|0
001WR41PYNWXCAE2X4|Kettering Care Centre|3313 Wilmington Pike|Kettering|OH|45429|HV|0|0
001B7XZAA3AFALS9GP|Kettering Senior Campus|3313 Wilmington Pk|Kettering|OH|45429|CT|0|0
00159PL81N38KM4FHM|Monroe Gardens Care Center|750 Stewart Rd|Monroe|MI|48162|HV|0|0
001RJU1X4NBWC1Q0G7|Riverbend Manor Care Center|150 River St|Chagrin Falls|OH|44022|BH|0|0
0017MN2JYAJBDS8WQZ|Sunny Acres Retirement Home|8060 Willow Creek Lane|Portage|MI|49024|BH|0|0"""
P = {"BH": "0015QAPLGS3FVYEEEM", "HV": "001FJZYHR7MLFMNPLL", "CT": "001FWSQ30SFW6S7604", "": ""}
ACCOUNTS = []
for l in ROWS.splitlines():
    i, n, st, c, s, z, p, rev, ar = l.split("|")
    ACCOUNTS.append(dict(account_id=i, name=n, billing_street=st, billing_city=c, billing_state=s, billing_zip=z,
                         parent_id=P[p], status="Active", note="", phone="x", lifetime_revenue=float(rev),
                         outstanding_ar=float(ar), duplicate_of_account="", chow_current_account="", parent_name=""))
