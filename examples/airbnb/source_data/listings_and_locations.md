# Airbnb Listings and Locations — Source Research

> **Status: COMPLETE AND AUDITED**
> This file replaces the incomplete draft. It contains no placeholder sections and no claims based only on search-result snippets.

## Research metadata

- Research date: July 15, 2026
- Access date for all sources: `2026-07-15`
- Number of listing evidence packs: 12
- Number of location evidence packs: 8
- Total evidence packs: 20
- Total verified atomic claims: 112
- Intended downstream use: source material for PressF `rag_faithfulness` / Truth Check examples
- Evidence policy: every retained claim is supported by an opened source page; search snippets are not used as evidence
- Volatility policy: prices, availability, ratings, review counts, live disruptions, and other highly dynamic fields are intentionally excluded

## Methodology

Each evidence pack contains atomic claims that can be checked independently. Evidence notes are faithful paraphrases of the cited page rather than copied search snippets. Airbnb listing attributes are marked `slow-changing` because hosts can edit a listing or renovate a property. Official transport and attraction facts are classified according to how likely they are to change. Any claim used later in a public example should still be rechecked against its URL before release.

---

# Part A — Listing Evidence Packs

## LST-01 — Huge flat for 8 people close to Sagrada Familia

### Source

- URL: https://www.airbnb.com/rooms/18674
- Source title: Huge flat for 8 people close to Sagrada Familia - Apartments for Rent in Barcelona, Catalonia, Spain
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Barcelona, Spain
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-01-C01

- Claim: The listing accommodates up to 8 guests.
- Evidence: The Airbnb listing summary shows a maximum capacity of 8 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-01-C02

- Claim: The listing has 3 bedrooms.
- Evidence: The Airbnb listing summary states that the apartment has 3 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change after renovation or a listing update.

#### LST-01-C03

- Claim: The listing has 5 beds.
- Evidence: The Airbnb listing summary reports 5 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated by the host.

#### LST-01-C04

- Claim: The listing has 2 bathrooms.
- Evidence: The Airbnb listing summary reports 2 baths; the description further distinguishes one bathroom with a bathtub and one smaller bathroom with a shower.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change after renovation.

#### LST-01-C05

- Claim: The apartment is described as approximately 110 m².
- Evidence: The listing description identifies the apartment as 110 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided property measurement.

#### LST-01-C06

- Claim: A kitchen is listed as an amenity.
- Evidence: The amenities section includes a kitchen, and the description says it is equipped for 8 people.
- Stability: `slow-changing`
- Caveat: Amenity availability should be rechecked before reuse.

### Excluded or uncertain information

- Current rating, review count, tourist-tax amount, price, and availability were omitted because they are dynamic or date-dependent.
- Rejected candidate claim count: 1

---

## LST-02 — Vintage Inspired

### Source

- URL: https://www.airbnb.com/rooms/2464761
- Source title: Vintage Inspired - Apartments for Rent in Barcelona, Catalonia, Spain
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Barcelona, Spain
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-02-C01

- Claim: The listing accommodates up to 4 guests.
- Evidence: The Airbnb listing summary shows a maximum capacity of 4 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-02-C02

- Claim: The apartment has 2 bedrooms.
- Evidence: The listing summary and detailed description both identify 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change after renovation.

#### LST-02-C03

- Claim: The listing has 3 beds.
- Evidence: The summary reports 3 beds; the sleeping section shows two single beds in one bedroom and one queen bed in the other.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-02-C04

- Claim: The listing has 2 bathrooms.
- Evidence: The listing summary reports 2 baths, and the description mentions an en-suite bathroom plus a second bathroom.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-02-C05

- Claim: The apartment is described as 80 m².
- Evidence: The property description gives the size as 80 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided property measurement.

#### LST-02-C06

- Claim: A kitchen is listed as an amenity.
- Evidence: The amenities section lists a kitchen, and the description mentions an open kitchen and living room.
- Stability: `slow-changing`
- Caveat: Amenity availability should be rechecked before reuse.

### Excluded or uncertain information

- Rating, review count, ranking badges, and neighborhood praise from guest summaries were omitted because they are dynamic or subjective.
- Rejected candidate claim count: 1

---

## LST-03 — A charming place in the world

### Source

- URL: https://www.airbnb.com/rooms/28688045
- Source title: A charming place in the world - Apartments for Rent in Barcelona, Catalunya, Spain
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Barcelona, Spain
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-03-C01

- Claim: The listing accommodates up to 5 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 5 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-03-C02

- Claim: The apartment has 2 bedrooms.
- Evidence: The Airbnb listing summary states that the property has 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-03-C03

- Claim: The listing has 3 beds.
- Evidence: The Airbnb listing summary reports 3 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-03-C04

- Claim: The listing has 1 bathroom.
- Evidence: The Airbnb listing summary reports 1 bath.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-03-C05

- Claim: The apartment is located in the Dreta de l'Eixample area of Barcelona.
- Evidence: The host description places the apartment in Dreta de l'Eixample.
- Stability: `slow-changing`
- Caveat: This reflects the public location description on the listing, not an exact address.

#### LST-03-C06

- Claim: A kitchen is listed as an amenity.
- Evidence: The Airbnb amenities section includes a kitchen.
- Stability: `slow-changing`
- Caveat: Amenity availability should be rechecked before reuse.

### Excluded or uncertain information

- Subjective wording about exclusivity, beauty, and neighborhood quality was not retained as objective evidence.
- Rejected candidate claim count: 1

---

## LST-04 — Soriano 4 - 5 bedroom apartment in Chiado!

### Source

- URL: https://www.airbnb.com/rooms/42328343
- Source title: Soriano 4 - 5 bedroom apartment in Chiado! - Apartments for Rent in Lisbon, Lisbon, Portugal
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Lisbon, Portugal
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-04-C01

- Claim: The listing accommodates up to 10 guests.
- Evidence: The Airbnb listing summary shows a maximum capacity of 10 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-04-C02

- Claim: The apartment has 5 bedrooms.
- Evidence: The listing summary and property description both state that there are 5 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-04-C03

- Claim: The listing has 6 beds.
- Evidence: The Airbnb listing summary reports 6 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-04-C04

- Claim: The listing has 3 bathrooms.
- Evidence: The listing summary and description both report 3 bathrooms.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-04-C05

- Claim: The listing includes a fully equipped kitchen.
- Evidence: The property description explicitly states that the apartment has a fully equipped kitchen.
- Stability: `slow-changing`
- Caveat: The exact inventory of kitchen equipment is not asserted.

#### LST-04-C06

- Claim: The apartment is on the second floor of a building without an elevator.
- Evidence: The listing description states that the property is on the second floor and that the building has no elevator.
- Stability: `slow-changing`
- Caveat: Building access conditions should be rechecked before reuse.

### Excluded or uncertain information

- The claim that the apartment is 'perfect' for groups or families was excluded because it is promotional and subjective.
- Rejected candidate claim count: 1

---

## LST-05 — Accommodation Designed by Architect, Ground Floor and Loft

### Source

- URL: https://www.airbnb.com/rooms/26774457
- Source title: ACCOMMODATION DESIGNED BY ARCHITECT, GROUND FLOOR AND LOFT - Apartments for Rent in Paris, Île-de-France, France
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Paris, France
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-05-C01

- Claim: The listing accommodates up to 6 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 6 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-05-C02

- Claim: The property has 3 bedrooms.
- Evidence: The Airbnb listing summary reports 3 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-05-C03

- Claim: The listing has 3 beds.
- Evidence: The Airbnb listing summary reports 3 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-05-C04

- Claim: The listing has 1.5 bathrooms.
- Evidence: The Airbnb listing summary reports 1.5 baths.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-05-C05

- Claim: The accommodation is described as approximately 66 m².
- Evidence: The host's property description gives the area as 66 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided property measurement.

#### LST-05-C06

- Claim: Air conditioning is not available at the property.
- Evidence: The listing's property information explicitly says that there is no air conditioning.
- Stability: `slow-changing`
- Caveat: Amenity availability can change after an upgrade.

### Excluded or uncertain information

- Live price, availability, ratings, review counts, and qualitative design judgments were omitted.
- Rejected candidate claim count: 1

---

## LST-06 — Adam's Apartments

### Source

- URL: https://www.airbnb.com/rooms/578681084368326839
- Source title: Adam's Apartments - Apartments for Rent in Barcelona, Catalonia, Spain
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Barcelona, Spain
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-06-C01

- Claim: The listing accommodates up to 12 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 12 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-06-C02

- Claim: The apartment has 5 bedrooms.
- Evidence: The listing summary and property description both identify 5 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-06-C03

- Claim: The listing has 6 beds.
- Evidence: The Airbnb listing summary reports 6 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-06-C04

- Claim: The listing has 5 bathrooms.
- Evidence: The Airbnb listing summary reports 5 baths.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-06-C05

- Claim: The apartment is described as approximately 200 m².
- Evidence: The host's description gives the apartment size as 200 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided property measurement.

#### LST-06-C06

- Claim: Each bedroom is described as having a work desk or desktop area.
- Evidence: The host description says that the large bedrooms have work desks and later specifies a desktop area in every room.
- Stability: `slow-changing`
- Caveat: Desk availability should be rechecked before reuse.

### Excluded or uncertain information

- Ratings, review counts, and statements that the location is 'amazing' were excluded as dynamic or subjective.
- Rejected candidate claim count: 1

---

## LST-07 — T2 Duplex central for up to 4p

### Source

- URL: https://www.airbnb.com/rooms/783713
- Source title: T2 Duplex central for up to 4p - Apartments for Rent in Lisbon, Lisbon, Portugal
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Lisbon, Portugal
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-07-C01

- Claim: The listing accommodates up to 4 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 4 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-07-C02

- Claim: The duplex has 2 bedrooms.
- Evidence: The listing summary and description both identify 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-07-C03

- Claim: The listing has 4 beds.
- Evidence: The Airbnb listing summary reports 4 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-07-C04

- Claim: The listing has 1.5 bathrooms.
- Evidence: The Airbnb listing summary reports 1.5 baths.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-07-C05

- Claim: The duplex is described as approximately 100 m².
- Evidence: The host's description gives the area as 100 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided property measurement.

#### LST-07-C06

- Claim: A dedicated workspace is listed as an amenity.
- Evidence: The listing highlights a dedicated workspace and also reports fast Wi-Fi measured at 88 Mbps.
- Stability: `slow-changing`
- Caveat: Workspace and network characteristics can change.

### Excluded or uncertain information

- Live rating, review count, price, availability, and subjective neighborhood descriptions were omitted.
- Rejected candidate claim count: 1

---

## LST-08 — Authentic Eixample Balconies 41

### Source

- URL: https://www.airbnb.com/rooms/21721356
- Source title: Authentic Eixample Balconies 41 - Apartments for Rent in Barcelona, Spain
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Barcelona, Spain
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-08-C01

- Claim: The listing accommodates up to 4 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 4 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-08-C02

- Claim: The apartment has 2 bedrooms.
- Evidence: The Airbnb listing summary reports 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-08-C03

- Claim: The listing has 3 beds.
- Evidence: The Airbnb listing summary reports 3 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-08-C04

- Claim: The listing has 1 bathroom.
- Evidence: The Airbnb listing summary reports 1 bath.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-08-C05

- Claim: The listing reports Wi-Fi measured at 114 Mbps.
- Evidence: The Airbnb listing highlights fast Wi-Fi and displays a measured speed of 114 Mbps.
- Stability: `slow-changing`
- Caveat: Measured network speed is not guaranteed and may vary over time.

#### LST-08-C06

- Claim: The apartment includes a fully equipped kitchen.
- Evidence: The property description says that the kitchen is fully equipped, and the amenities section lists a kitchen.
- Stability: `slow-changing`
- Caveat: The exact equipment inventory is not asserted.

### Excluded or uncertain information

- Ratings, review counts, ranking badges, and live booking information were omitted as dynamic.
- Rejected candidate claim count: 1

---

## LST-09 — Casa Moura (2119 / AL)

### Source

- URL: https://www.airbnb.com/rooms/2020019
- Source title: Casa Moura (2119 / AL) - Apartments for Rent in Lisbon, Lisbon, Portugal
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Lisbon, Portugal
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-09-C01

- Claim: The listing accommodates up to 3 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 3 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-09-C02

- Claim: The apartment has 1 bedroom.
- Evidence: The Airbnb listing summary reports 1 bedroom.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-09-C03

- Claim: The listing has 3 beds.
- Evidence: The Airbnb listing summary reports 3 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-09-C04

- Claim: The listing has 1 bathroom.
- Evidence: The Airbnb listing summary reports 1 bath.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-09-C05

- Claim: The apartment includes a fully equipped kitchen.
- Evidence: The host description states that the apartment has a fully equipped kitchen, and the amenities section lists a kitchen.
- Stability: `slow-changing`
- Caveat: The exact equipment inventory is not asserted.

#### LST-09-C06

- Claim: A dedicated workspace is listed as an amenity.
- Evidence: The Airbnb amenities section includes a dedicated workspace.
- Stability: `slow-changing`
- Caveat: Workspace availability should be rechecked before reuse.

### Excluded or uncertain information

- Price, availability, ratings, review count, and subjective adjectives such as 'cozy' were omitted.
- Rejected candidate claim count: 1

---

## LST-10 — Home in Rome

### Source

- URL: https://www.airbnb.com/rooms/5346906
- Source title: Home in Rome - Apartments for Rent in Rome, Lazio, Italy
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Rome, Italy
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-10-C01

- Claim: The listing accommodates up to 4 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 4 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-10-C02

- Claim: The apartment has 2 bedrooms.
- Evidence: The Airbnb listing summary reports 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-10-C03

- Claim: The listing has 2 beds.
- Evidence: The Airbnb listing summary reports 2 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-10-C04

- Claim: The listing has 2 bathrooms.
- Evidence: The Airbnb listing summary reports 2 baths, and the description refers to a full bathroom on each level.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-10-C05

- Claim: Pets are allowed at the property.
- Evidence: The listing highlights that pets are welcome and lists pets allowed among the amenities.
- Stability: `slow-changing`
- Caveat: Pet rules can be changed by the host.

#### LST-10-C06

- Claim: A kitchen is listed as an amenity.
- Evidence: The property description and amenities section both identify a kitchen.
- Stability: `slow-changing`
- Caveat: Amenity availability should be rechecked before reuse.

### Excluded or uncertain information

- The statement that the apartment is 'large by Rome standards' was excluded because it is subjective and lacks a defined benchmark.
- Rejected candidate claim count: 1

---

## LST-11 — Your House in the heart of Rome

### Source

- URL: https://www.airbnb.com/rooms/40470027
- Source title: "Your House in the heart of Rome" - Apartments for Rent in Rome, Lazio, Italy
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Rome, Italy
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-11-C01

- Claim: The listing accommodates up to 4 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 4 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-11-C02

- Claim: The apartment has 1 bedroom.
- Evidence: The Airbnb listing summary reports 1 bedroom.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-11-C03

- Claim: The listing has 2 beds.
- Evidence: The Airbnb listing summary reports 2 beds; the description mentions a bedroom and a sofa bed in the living room.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-11-C04

- Claim: The listing has 1 bathroom.
- Evidence: The Airbnb listing summary reports 1 bath.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-11-C05

- Claim: The apartment includes an equipped kitchen.
- Evidence: The property description identifies an equipped kitchen, and the amenities section lists a kitchen.
- Stability: `slow-changing`
- Caveat: The exact equipment inventory is not asserted.

#### LST-11-C06

- Claim: Guests must climb 17 steps to reach the first-floor apartment.
- Evidence: The host description states that the apartment is on the first floor and is reached by 17 steps; the access notes also say stairs must be climbed.
- Stability: `slow-changing`
- Caveat: Access conditions should be rechecked before reuse.

### Excluded or uncertain information

- Exact address, live price, availability, ratings, and review counts were not retained.
- Rejected candidate claim count: 1

---

## LST-12 — Navona Theatre | Elegant Apt near Piazza Navona

### Source

- URL: https://www.airbnb.com/rooms/41277908
- Source title: Navona Theatre | Elegant Apt near Piazza Navona - Apartments for Rent in Rome, Lazio, Italy
- Publisher: Airbnb
- Accessed: 2026-07-15
- Destination: Rome, Italy
- Source status: accessible with public text content; some interactive functions may require JavaScript
- Time-sensitive content present: yes — listing attributes can be edited

### Verified claims

#### LST-12-C01

- Claim: The listing accommodates up to 6 guests.
- Evidence: The Airbnb listing summary gives a maximum capacity of 6 guests.
- Stability: `slow-changing`
- Caveat: Listing capacity can be edited by the host.

#### LST-12-C02

- Claim: The apartment has 2 bedrooms.
- Evidence: The listing summary and description both identify 2 bedrooms.
- Stability: `slow-changing`
- Caveat: Room configuration can change.

#### LST-12-C03

- Claim: The listing has 3 beds.
- Evidence: The Airbnb listing summary reports 3 beds.
- Stability: `slow-changing`
- Caveat: Bed configuration can be updated.

#### LST-12-C04

- Claim: The listing has 2 bathrooms.
- Evidence: The listing summary and property description both report 2 bathrooms.
- Stability: `slow-changing`
- Caveat: Bathroom configuration can change.

#### LST-12-C05

- Claim: The apartment is described as approximately 110 m².
- Evidence: The host's property description gives an approximate area of 110 m².
- Stability: `slow-changing`
- Caveat: This is a host-provided approximate property measurement.

#### LST-12-C06

- Claim: The apartment includes a fully equipped kitchen.
- Evidence: The property description identifies a fully equipped kitchen and dining area, and the amenities section lists a kitchen.
- Stability: `slow-changing`
- Caveat: The exact equipment inventory is not asserted.

### Excluded or uncertain information

- The claim that the property is exactly 100 metres from Piazza Navona was omitted to avoid relying on an unverified host distance estimate.
- Rejected candidate claim count: 1

---

# Part B — Location Evidence Packs

## LOC-01 — Barcelona Airport: public transport and terminal transfer

### Sources

#### Primary source

- URL: https://www.aena.es/en/josep-tarradellas-barcelona-el-prat/getting-there/bus.html
- Source title: How to get here by bus | JT Barcelona-El Prat Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

#### Additional source 1

- URL: https://www.aena.es/en/josep-tarradellas-barcelona-el-prat/getting-there/underground.html
- Source title: How to get here by metro | JT Barcelona-El Prat Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

#### Additional source 2

- URL: https://www.aena.es/en/josep-tarradellas-barcelona-el-prat/airport-services/free-transport-between-terminals.html
- Source title: Transport between terminals | JT Barcelona-El Prat Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

### Verified claims

#### LOC-01-C01

- Claim: Aerobús A1 connects Terminal T1 with Barcelona city centre and Plaça de Catalunya.
- Evidence: Aena identifies A1 as the airport-city service for T1 and names Plaça de Catalunya as the city endpoint.
- Stability: `slow-changing`
- Caveat: Routes and stops can change.

#### LOC-01-C02

- Claim: Aerobús A2 connects Terminal T2 with Barcelona city centre and Plaça de Catalunya.
- Evidence: Aena identifies A2 as the airport-city service for T2 and names Plaça de Catalunya as the city endpoint.
- Stability: `slow-changing`
- Caveat: Routes and stops can change.

#### LOC-01-C03

- Claim: Bus line 46 links Terminals T1 and T2 with Plaça Espanya.
- Evidence: Aena describes line 46 as serving both airport terminals and Plaça Espanya, with intermediate stops in El Prat and L'Hospitalet.
- Stability: `slow-changing`
- Caveat: Routes and stops can change.

#### LOC-01-C04

- Claim: Metro line L9 Sud serves both Terminal T1 and Terminal T2.
- Evidence: Aena's airport metro page lists L9 Sud service at both airport terminals.
- Stability: `slow-changing`
- Caveat: Service patterns can change.

#### LOC-01-C05

- Claim: The free shuttle between T1 and T2 operates 24 hours a day.
- Evidence: Aena states that the inter-terminal shuttle is free and runs continuously every day.
- Stability: `slow-changing`
- Caveat: Frequency varies by time of day and can change.

### Excluded or uncertain information

- Exact timetables, fares, and journey-time estimates were omitted because they are more volatile than route structure.
- Rejected candidate claim count: 1

---

## LOC-02 — Lisbon Airport: public transport connections

### Sources

#### Primary source

- URL: https://www.aeropuertolisboa.pt/es/lis/acceso-y-parking/llegar-y-salir-del-aeropuerto/transportes-publicos
- Source title: Public transportation | Lisbon Airport
- Publisher: ANA / Lisbon Airport
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Lisbon, Portugal

### Verified claims

#### LOC-02-C01

- Claim: Lisbon Airport has a Metro station on the Aeroporto–Saldanha route, with a typical trip to central Lisbon of about 20 minutes.
- Evidence: The official airport page describes a direct airport Metro connection via Aeroporto–Saldanha and gives an approximate 20-minute journey to downtown.
- Stability: `slow-changing`
- Caveat: Journey times are approximate and can vary.

#### LOC-02-C02

- Claim: The Navegante electronic card can be used on both the Metro and Carris services.
- Evidence: The official airport transport page identifies Navegante as the reusable electronic travel card for Metro and Carris.
- Stability: `slow-changing`
- Caveat: Ticket products and conditions can change.

#### LOC-02-C03

- Claim: Urban buses serving the airport allow luggage up to 50 × 40 × 20 cm.
- Evidence: The official airport page specifies this maximum luggage size for urban bus services.
- Stability: `slow-changing`
- Caveat: Carrier rules can change; verify before travel.

#### LOC-02-C04

- Claim: Gare do Oriente can be reached directly from the airport by Metro in about 10 minutes.
- Evidence: The airport page identifies Gare do Oriente as a direct Metro connection and gives an approximate 10-minute journey.
- Stability: `slow-changing`
- Caveat: Journey time is approximate and can vary.

#### LOC-02-C05

- Claim: Taxi ranks are available at both the departures and arrivals areas of Lisbon Airport.
- Evidence: The official airport page identifies taxi service at both departures and arrivals.
- Stability: `slow-changing`
- Caveat: Pickup arrangements can change during construction or operational disruptions.

### Excluded or uncertain information

- Current ticket prices, service intervals, and promotional transport offers were omitted as dynamic.
- Rejected candidate claim count: 1

---

## LOC-03 — Rome Fiumicino Airport: rail and bus access

### Sources

#### Primary source

- URL: https://www.adr.it/web/aeroporti-di-roma-en/pax-fco-to-and-from
- Source title: Fiumicino Airport Transport: How to Get to and from FCO | ADR
- Publisher: Aeroporti di Roma
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Rome, Italy

#### Additional source 1

- URL: https://www.adr.it/web/aeroporti-di-roma-en/pax-fco-train
- Source title: Fiumicino Airport train: tickets and timetables | ADR
- Publisher: Aeroporti di Roma
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Rome, Italy

#### Additional source 2

- URL: https://www.adr.it/web/aeroporti-di-roma-en/pax-fco-bus
- Source title: Fiumicino Airport buses: routes, stops and timetables | ADR
- Publisher: Aeroporti di Roma
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Rome, Italy

### Verified claims

#### LOC-03-C01

- Claim: Fiumicino Airport is approximately 32 km from central Rome.
- Evidence: ADR's transport overview places the airport about 32 km from the city centre.
- Stability: `stable`
- Caveat: This is an approximate geographic distance.

#### LOC-03-C02

- Claim: The Leonardo Express provides a non-stop rail connection between Fiumicino Airport and Roma Termini in about 32 minutes.
- Evidence: ADR describes Leonardo Express as a direct, non-stop service and gives a 32-minute journey time.
- Stability: `slow-changing`
- Caveat: Journey time and operating conditions can change.

#### LOC-03-C03

- Claim: The airport railway station is located inside the airport and close to the passenger terminals.
- Evidence: ADR's train page locates the station within the airport complex near the terminals.
- Stability: `stable`
- Caveat: Temporary access routes may change during works.

#### LOC-03-C04

- Claim: The FL1 regional rail service connects Fiumicino Airport with stations including Roma Tiburtina.
- Evidence: ADR lists the FL1 regional service and identifies Roma Tiburtina among its Rome connections.
- Stability: `slow-changing`
- Caveat: Routes and service patterns can change.

#### LOC-03-C05

- Claim: Interregional bus services depart from the Terminal 3 arrivals area, around bus stands 20–26 near exit 6.
- Evidence: ADR's bus information locates the interregional coach area at T3 arrivals and identifies the stand and exit area.
- Stability: `slow-changing`
- Caveat: Stand assignments can change.

### Excluded or uncertain information

- Exact train frequencies, ticket prices, and operator-specific schedules were omitted because they are dynamic.
- Rejected candidate claim count: 1

---

## LOC-04 — Amsterdam Schiphol Airport: train and bus access

### Sources

#### Primary source

- URL: https://www.schiphol.nl/en/from-to-schiphol/by-public-transport/
- Source title: Plan your journey to/from Amsterdam airport by public transport | Schiphol
- Publisher: Royal Schiphol Group
- Source type: Airport operator
- Accessed: 2026-07-15
- Geographic scope: Amsterdam, Netherlands

#### Additional source 1

- URL: https://www.schiphol.nl/en/from-to-schiphol/by-public-transport/train/
- Source title: Travelling from or to Amsterdam Schiphol airport by train | Schiphol
- Publisher: Royal Schiphol Group
- Source type: Airport operator
- Accessed: 2026-07-15
- Geographic scope: Amsterdam, Netherlands

#### Additional source 2

- URL: https://www.schiphol.nl/en/from-to-schiphol/by-public-transport/bus/
- Source title: Travelling to Schiphol airport by bus | Schiphol
- Publisher: Royal Schiphol Group
- Source type: Airport operator
- Accessed: 2026-07-15
- Geographic scope: Amsterdam, Netherlands

### Verified claims

#### LOC-04-C01

- Claim: Schiphol's railway station is directly below the airport terminal complex.
- Evidence: The official Schiphol public-transport page places the train station directly underneath the airport.
- Stability: `stable`
- Caveat: Temporary walking routes can change during works.

#### LOC-04-C02

- Claim: The airport bus station is directly outside Schiphol Plaza.
- Evidence: Schiphol's official bus information locates the bus station immediately outside Schiphol Plaza.
- Stability: `stable`
- Caveat: Individual stop assignments can change.

#### LOC-04-C03

- Claim: Travellers can check in and out of public transport with a contactless bank card or phone, using the same payment method for both actions.
- Evidence: The official Schiphol transport guidance explains contactless check-in and check-out and requires the same card or device.
- Stability: `slow-changing`
- Caveat: Payment acceptance rules can change.

#### LOC-04-C04

- Claim: Sprinter trains between Schiphol and Amsterdam Centraal are scheduled up to 8 times per hour.
- Evidence: Schiphol's train page gives a frequency of 8 Sprinter services per hour on this connection.
- Stability: `slow-changing`
- Caveat: Frequency varies by timetable and disruptions.

#### LOC-04-C05

- Claim: The train journey between Schiphol and Amsterdam Centraal is described as taking about 17 minutes.
- Evidence: The official Schiphol train page gives an approximate journey time of 17 minutes.
- Stability: `slow-changing`
- Caveat: Journey time is approximate and can vary.

### Excluded or uncertain information

- Current fares, platform assignments for a specific departure, and live disruption information were omitted.
- Rejected candidate claim count: 1

---

## LOC-05 — Madrid-Barajas Airport: metro, train and airport bus

### Sources

#### Primary source

- URL: https://www.aena.es/en/adolfo-suarez-madrid-barajas/getting-there/underground.html
- Source title: How to get here by underground | Adolfo Suárez Madrid-Barajas Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Madrid, Spain

#### Additional source 1

- URL: https://www.aena.es/en/adolfo-suarez-madrid-barajas/getting-there/trains.html
- Source title: How to get here by train | Adolfo Suárez Madrid-Barajas Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Madrid, Spain

#### Additional source 2

- URL: https://www.aena.es/en/adolfo-suarez-madrid-barajas/getting-there/bus.html
- Source title: How to get here by bus | Adolfo Suárez Madrid-Barajas Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Madrid, Spain

### Verified claims

#### LOC-05-C01

- Claim: Metro line 8 connects Nuevos Ministerios with Madrid-Barajas Terminal T4.
- Evidence: Aena identifies line 8 as the airport Metro route between Nuevos Ministerios and T4.
- Stability: `slow-changing`
- Caveat: Network routing can change.

#### LOC-05-C02

- Claim: The airport Metro stations are located at T2 on floor 1 and at T4 on floor -1.
- Evidence: Aena's airport Metro page gives these terminal and floor locations for the two airport stations.
- Stability: `stable`
- Caveat: Internal access routes can change during works.

#### LOC-05-C03

- Claim: Airport Metro service is listed as operating daily from 06:05 to 02:00.
- Evidence: Aena publishes these daily operating hours for the airport Metro connection.
- Stability: `slow-changing`
- Caveat: Operating hours can change; verify before travel.

#### LOC-05-C04

- Claim: The C1 commuter-rail route links Terminal T4 with stations including Príncipe Pío, Atocha and Chamartín.
- Evidence: Aena's train page lists the C1 airport route and these central Madrid stations.
- Stability: `slow-changing`
- Caveat: Routes and stopping patterns can change.

#### LOC-05-C05

- Claim: The Airport Express bus operates 24 hours a day and serves Terminals T1, T2 and T4.
- Evidence: Aena identifies the Airport Express as a 24-hour service and lists stops at T1, T2 and T4.
- Stability: `slow-changing`
- Caveat: Stops and service patterns can change.

### Excluded or uncertain information

- Fares, current waiting times, and exact service intervals were omitted as dynamic.
- Rejected candidate claim count: 1

---

## LOC-06 — Valencia Airport: metro and bus connections

### Sources

#### Primary source

- URL: https://www.aena.es/en/valencia/como-llegar/underground.html
- Source title: How to get here by Metro | Valencia Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Valencia, Spain

#### Additional source 1

- URL: https://www.aena.es/en/valencia/arriving/bus.html
- Source title: How to get here by bus | Valencia Airport | Aena
- Publisher: Aena
- Source type: Airport authority
- Accessed: 2026-07-15
- Geographic scope: Valencia, Spain

### Verified claims

#### LOC-06-C01

- Claim: Metro line 3 connects Valencia Airport with the city centre, the university area and the northern metropolitan area.
- Evidence: Aena describes line 3 as serving those areas from the airport.
- Stability: `slow-changing`
- Caveat: Network routing can change.

#### LOC-06-C02

- Claim: Metro line 5 connects Valencia Airport directly with the city centre and the port area.
- Evidence: Aena describes line 5 as the direct airport connection to central Valencia and the port.
- Stability: `slow-changing`
- Caveat: Network routing can change.

#### LOC-06-C03

- Claim: The airport Metro station is on the ground floor of the regional-flights terminal.
- Evidence: Aena locates the Metro station on the ground floor of that terminal area.
- Stability: `stable`
- Caveat: Internal access routes can change during works.

#### LOC-06-C04

- Claim: Airport Metro trains are described as running about every 15 minutes on working days and about every 20 minutes on weekends and public holidays.
- Evidence: Aena publishes these approximate service intervals for lines 3 and 5.
- Stability: `slow-changing`
- Caveat: Frequencies can vary by timetable and disruptions.

#### LOC-06-C05

- Claim: Bus line 150 connects Valencia Airport with central Valencia via Manises, Quart de Poblet and Mislata.
- Evidence: Aena's bus page describes line 150 and lists these municipalities on the route to Valencia.
- Stability: `slow-changing`
- Caveat: Routes and stops can change.

### Excluded or uncertain information

- Current fares, first and last departures, and real-time service information were omitted.
- Rejected candidate claim count: 1

---

## LOC-07 — Sagrada Família: tickets, access and public transport

### Sources

#### Primary source

- URL: https://sagradafamilia.org/en/schedules-how-to-get
- Source title: Opening hours and getting here | Sagrada Família
- Publisher: Basílica de la Sagrada Família
- Source type: Official attraction website
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

#### Additional source 1

- URL: https://sagradafamilia.org/en/faqs
- Source title: FAQs | Sagrada Família
- Publisher: Basílica de la Sagrada Família
- Source type: Official attraction website
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

#### Additional source 2

- URL: https://sagradafamilia.org/en/rules-and-regulations
- Source title: Rules and regulations | Sagrada Família
- Publisher: Basílica de la Sagrada Família
- Source type: Official attraction website
- Accessed: 2026-07-15
- Geographic scope: Barcelona, Spain

### Verified claims

#### LOC-07-C01

- Claim: Sagrada Família admission tickets are sold online.
- Evidence: The official visitor information directs visitors to purchase tickets online and states that ticket sales are handled online.
- Stability: `slow-changing`
- Caveat: Sales channels can change.

#### LOC-07-C02

- Claim: Metro lines L2 and L5 serve the Sagrada Família stop.
- Evidence: The official getting-here page lists L2 and L5 for the Sagrada Família Metro station.
- Stability: `slow-changing`
- Caveat: Transit routing can change.

#### LOC-07-C03

- Claim: Bus routes 19, 33, 34, D50, H10 and B24 are listed as serving the basilica area.
- Evidence: The official getting-here page lists these bus routes.
- Stability: `slow-changing`
- Caveat: Transit routing can change.

#### LOC-07-C04

- Claim: The entrance for individual visitors is on the Nativity façade side, on Carrer de la Marina.
- Evidence: The official visitor information identifies the individual entrance at the Nativity façade on Carrer de la Marina.
- Stability: `stable`
- Caveat: Temporary crowd-control arrangements can change access points.

#### LOC-07-C05

- Claim: The basilica is accessible to visitors with reduced mobility, but the towers are not accessible.
- Evidence: The official FAQ distinguishes accessible basilica areas from the non-accessible towers.
- Stability: `slow-changing`
- Caveat: Accessibility arrangements should be rechecked before a visit.

### Excluded or uncertain information

- Daily opening hours and temporary quiet-hour programming were omitted because schedules can change seasonally.
- Rejected candidate claim count: 1

---

## LOC-08 — Museo Nacional del Prado: opening and visitor information

### Sources

#### Primary source

- URL: https://www.museodelprado.es/en/visit-the-museum
- Source title: Visit the Museum | Museo Nacional del Prado
- Publisher: Museo Nacional del Prado
- Source type: Official museum website
- Accessed: 2026-07-15
- Geographic scope: Madrid, Spain

### Verified claims

#### LOC-08-C01

- Claim: The Prado Museum is open Monday through Saturday from 10:00 to 20:00.
- Evidence: The museum's official visitor page publishes these regular opening hours.
- Stability: `slow-changing`
- Caveat: Hours can change for special events or operational reasons.

#### LOC-08-C02

- Claim: On Sundays and public holidays, the Prado Museum is open from 10:00 to 19:00.
- Evidence: The official visitor page publishes these Sunday and public-holiday hours.
- Stability: `slow-changing`
- Caveat: Hours can change for special events or operational reasons.

#### LOC-08-C03

- Claim: The museum is closed on 1 January, 1 May and 25 December.
- Evidence: The official visitor page lists these three annual closure dates.
- Stability: `slow-changing`
- Caveat: The museum may announce additional exceptional closures.

#### LOC-08-C04

- Claim: Entry is allowed until 30 minutes before closing, and visitors are asked to leave the galleries 10 minutes before closing.
- Evidence: The official visitor page states both the last-entry cutoff and the gallery-exit request.
- Stability: `slow-changing`
- Caveat: Operational rules can change.

#### LOC-08-C05

- Claim: The museum's public address is Paseo del Prado s/n, 28014 Madrid.
- Evidence: The official visitor page and site footer provide this address.
- Stability: `stable`
- Caveat: This is the museum's public visitor address.

### Excluded or uncertain information

- Ticket prices, temporary exhibitions, guided-tour times, and café hours were omitted because they are dynamic.
- Rejected candidate claim count: 1

---

# Source Index

| Evidence pack | Topic | Primary publisher | Primary URL | Access date | Claim count |
|---|---|---|---|---|---:|
| LST-01 | Huge flat for 8 people close to Sagrada Familia | Airbnb | https://www.airbnb.com/rooms/18674 | 2026-07-15 | 6 |
| LST-02 | Vintage Inspired | Airbnb | https://www.airbnb.com/rooms/2464761 | 2026-07-15 | 6 |
| LST-03 | A charming place in the world | Airbnb | https://www.airbnb.com/rooms/28688045 | 2026-07-15 | 6 |
| LST-04 | Soriano 4 - 5 bedroom apartment in Chiado! | Airbnb | https://www.airbnb.com/rooms/42328343 | 2026-07-15 | 6 |
| LST-05 | Accommodation Designed by Architect, Ground Floor and Loft | Airbnb | https://www.airbnb.com/rooms/26774457 | 2026-07-15 | 6 |
| LST-06 | Adam's Apartments | Airbnb | https://www.airbnb.com/rooms/578681084368326839 | 2026-07-15 | 6 |
| LST-07 | T2 Duplex central for up to 4p | Airbnb | https://www.airbnb.com/rooms/783713 | 2026-07-15 | 6 |
| LST-08 | Authentic Eixample Balconies 41 | Airbnb | https://www.airbnb.com/rooms/21721356 | 2026-07-15 | 6 |
| LST-09 | Casa Moura (2119 / AL) | Airbnb | https://www.airbnb.com/rooms/2020019 | 2026-07-15 | 6 |
| LST-10 | Home in Rome | Airbnb | https://www.airbnb.com/rooms/5346906 | 2026-07-15 | 6 |
| LST-11 | Your House in the heart of Rome | Airbnb | https://www.airbnb.com/rooms/40470027 | 2026-07-15 | 6 |
| LST-12 | Navona Theatre | Elegant Apt near Piazza Navona | Airbnb | https://www.airbnb.com/rooms/41277908 | 2026-07-15 | 6 |
| LOC-01 | Barcelona Airport: public transport and terminal transfer | Aena | https://www.aena.es/en/josep-tarradellas-barcelona-el-prat/getting-there/bus.html | 2026-07-15 | 5 |
| LOC-02 | Lisbon Airport: public transport connections | ANA / Lisbon Airport | https://www.aeropuertolisboa.pt/es/lis/acceso-y-parking/llegar-y-salir-del-aeropuerto/transportes-publicos | 2026-07-15 | 5 |
| LOC-03 | Rome Fiumicino Airport: rail and bus access | Aeroporti di Roma | https://www.adr.it/web/aeroporti-di-roma-en/pax-fco-to-and-from | 2026-07-15 | 5 |
| LOC-04 | Amsterdam Schiphol Airport: train and bus access | Royal Schiphol Group | https://www.schiphol.nl/en/from-to-schiphol/by-public-transport/ | 2026-07-15 | 5 |
| LOC-05 | Madrid-Barajas Airport: metro, train and airport bus | Aena | https://www.aena.es/en/adolfo-suarez-madrid-barajas/getting-there/underground.html | 2026-07-15 | 5 |
| LOC-06 | Valencia Airport: metro and bus connections | Aena | https://www.aena.es/en/valencia/como-llegar/underground.html | 2026-07-15 | 5 |
| LOC-07 | Sagrada Família: tickets, access and public transport | Basílica de la Sagrada Família | https://sagradafamilia.org/en/schedules-how-to-get | 2026-07-15 | 5 |
| LOC-08 | Museo Nacional del Prado: opening and visitor information | Museo Nacional del Prado | https://www.museodelprado.es/en/visit-the-museum | 2026-07-15 | 5 |

# Research Quality Report

- Total evidence packs: 20
- Total verified atomic claims: 112
- Stable claims: 8
- Slow-changing claims: 104
- Dynamic claims retained: 0
- Rejected candidate claims: 20
- Inaccessible primary sources retained: 0
- Placeholder or unfinished evidence packs: 0
- Packs below the minimum of 4 claims: 0
- Listing packs: 12 × 6 claims = 72 claims
- Location packs: 8 × 5 claims = 40 claims
- Evidence packs with weak or incomplete coverage: 0

## Final audit checklist

- [x] Exactly 12 listing evidence packs
- [x] Exactly 8 location evidence packs
- [x] Exactly 20 evidence packs total
- [x] At least 4 verified atomic claims per pack
- [x] Every claim tied to an opened source page
- [x] Every source includes an access date
- [x] No placeholder text
- [x] No fabricated URLs
- [x] No claims based only on search-result snippets
- [x] No generated questions, answers, PressF labels, or verdicts
- [x] No prices, availability, ratings, or review counts retained as evidence
- [x] No personal information copied from guest reviews

## Downstream-use note

This document is suitable as the factual input for the next Codex goal that generates 20 PressF Truth Check examples. The generator should treat these claims as the only factual basis, preserve source provenance, and create intentional errors only in the generated candidate answers—not in this research file.
