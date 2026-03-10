#!/usr/bin/env python3
import random
from pathlib import Path

def create_fake_contracts():
    """Create 10 fake contracts based on Tupperware/Osceola theme"""
    
    # Common entities from Exhibit document
    companies = ["Tupperware Brands Corporation", "TUPPERWARE", "Dart Container Corporation", "DART", "SFWMD", "TBCOM"]
    people = ["Connor", "Roehlk", "Sheehan", "Sheppard", "Greenberg", "Traurig", "Miranda", "Greenwald"]
    locations = ["Osceola County", "OSCEOLA", "Kissimmee", "Deerfield Beach", "DEERFIELD"]
    properties = ["Gatorland", "Blossom", "Trailside", "Crosslands", "Brightview", "Lakeside", "Rapallo", "Venezia", "Terre", "Cinque", "Solitude"]
    
    # Contract templates with varying sizes
    contracts = []
    
    # Contract 1: Short Purchase Agreement (15 pages)
    contract1 = f"""<!DOCTYPE html>
<html>
<head><title>Real Estate Purchase Agreement - Tupperware Property</title></head>
<body>
<h1>REAL ESTATE PURCHASE AGREEMENT</h1>

<p>This Purchase Agreement is entered into between {random.choice(companies)} ("Buyer") and {random.choice(people)} ("Seller") for the purchase of property located in {random.choice(locations)}.</p>

<h2>PROPERTY DESCRIPTION</h2>
<p>The property known as {random.choice(properties)} Development, located at 1234 Corporate Drive, {random.choice(locations)}, Florida 34741.</p>

<h2>PURCHASE PRICE</h2>
<p>The total purchase price is $2,500,000.00 (Two Million Five Hundred Thousand Dollars).</p>

<h2>BUYER INFORMATION</h2>
<p>Buyer: {random.choice(companies)}</p>
<p>Address: 14901 S Orange Blossom Trail, Orlando, FL 32837</p>
<p>Contact: {random.choice(people)}, Vice President</p>
<p>Phone: (407) 826-5050</p>
<p>Email: {random.choice(people).lower()}@tupperware.com</p>

<h2>SELLER INFORMATION</h2>
<p>Seller: {random.choice(people)} Development LLC</p>
<p>Address: 789 {random.choice(properties)} Boulevard, {random.choice(locations)}, FL 34746</p>
<p>Contact: {random.choice(people)}</p>
<p>SSN: 123-45-6789</p>

<h2>TERMS AND CONDITIONS</h2>
<p>1. Closing Date: March 15, 2024</p>
<p>2. Earnest Money: $50,000.00</p>
<p>3. Financing: Cash purchase by {random.choice(companies)}</p>
<p>4. Title Company: {random.choice(locations)} Title & Trust</p>

<h2>SIGNATURES</h2>
<p>Buyer: _________________________ Date: _________</p>
<p>{random.choice(people)}, for {random.choice(companies)}</p>

<p>Seller: _________________________ Date: _________</p>
<p>{random.choice(people)}</p>

""" + "\\n\\n".join([f"<p>Page {i} - Additional terms and conditions for the {random.choice(properties)} development project in {random.choice(locations)}. This involves coordination with {random.choice(companies)} and oversight by {random.choice(people)}.</p>" for i in range(3, 16)])

    contracts.append(("Tupperware_Property_Purchase_1.mhtml", contract1 + "</body></html>"))

    # Contract 2: Medium Lease Agreement (25 pages)
    contract2 = f"""<!DOCTYPE html>
<html>
<head><title>Commercial Lease Agreement - Tupperware Facility</title></head>
<body>
<h1>COMMERCIAL LEASE AGREEMENT</h1>

<p>This Lease Agreement is between {random.choice(companies)} as Tenant and {random.choice(properties)} Holdings LLC as Landlord.</p>

<h2>PREMISES</h2>
<p>The leased premises consist of 150,000 square feet of warehouse and office space located at {random.choice(properties)} Industrial Park, {random.choice(locations)}, Florida.</p>

<h2>TENANT DETAILS</h2>
<p>Tenant: {random.choice(companies)}</p>
<p>Primary Contact: {random.choice(people)}, Facilities Manager</p>
<p>Phone: (407) 826-5000</p>
<p>Federal Tax ID: 59-0806307</p>

<h2>LANDLORD DETAILS</h2>
<p>Landlord: {random.choice(properties)} Holdings LLC</p>
<p>Managing Partner: {random.choice(people)}</p>
<p>Address: 456 {random.choice(locations)} Parkway, Suite 200</p>
<p>Phone: (407) 555-0123</p>

<h2>LEASE TERMS</h2>
<p>Monthly Rent: $75,000.00</p>
<p>Security Deposit: $150,000.00</p>
<p>Lease Term: 10 years commencing January 1, 2024</p>

""" + "\\n\\n".join([f"<h3>Section {i}</h3><p>Detailed provisions regarding the use of the {random.choice(properties)} facility by {random.choice(companies)}. Maintenance responsibilities are shared between {random.choice(people)} (Tenant representative) and {random.choice(people)} (Landlord representative). All utilities for the {random.choice(locations)} location are included.</p>" for i in range(1, 21)])

    contracts.append(("Tupperware_Lease_Agreement_2.mhtml", contract2 + "</body></html>"))

    # Contract 3: Large Development Agreement (40 pages)
    contract3 = f"""<!DOCTYPE html>
<html>
<head><title>Master Development Agreement - Osceola Tupperware Campus</title></head>
<body>
<h1>MASTER DEVELOPMENT AGREEMENT</h1>
<h2>{random.choice(locations)} TUPPERWARE CORPORATE CAMPUS</h2>

<p>This Master Development Agreement is entered into between {random.choice(companies)}, a Delaware corporation, and {random.choice(locations)} County, Florida.</p>

<h2>PROJECT OVERVIEW</h2>
<p>Development of a 500-acre corporate campus in {random.choice(locations)} County, including:</p>
<ul>
<li>Corporate headquarters building</li>
<li>{random.choice(properties)} residential community</li>
<li>{random.choice(properties)} commercial district</li>
<li>Environmental preservation areas</li>
</ul>

<h2>DEVELOPMENT TEAM</h2>
<p>Project Manager: {random.choice(people)}</p>
<p>Lead Architect: {random.choice(people)} & Associates</p>
<p>Environmental Consultant: {random.choice(people)} Environmental Services</p>
<p>Legal Counsel: {random.choice(people)}, Esq.</p>

<h2>FINANCIAL DETAILS</h2>
<p>Total Project Cost: $250,000,000</p>
<p>Tupperware Investment: $180,000,000</p>
<p>County Incentives: $25,000,000</p>
<p>Federal Tax Credits: $15,000,000</p>

<h2>REGULATORY APPROVALS</h2>
<p>Environmental Impact Assessment by SFWMD</p>
<p>Zoning approval from {random.choice(locations)} County</p>
<p>Traffic impact study for {random.choice(properties)} corridor</p>

""" + "\\n\\n".join([f"<h3>Phase {i} Development</h3><p>This phase involves construction of the {random.choice(properties)} section of the campus. {random.choice(people)} will oversee coordination with {random.choice(companies)} and ensure compliance with {random.choice(locations)} County regulations. Environmental monitoring by {random.choice(people)} is required throughout this phase. The {random.choice(properties)} area will include both residential and commercial components, with {random.choice(people)} serving as the primary liaison with SFWMD for water management permits.</p>" for i in range(1, 31)])

    contracts.append(("Osceola_Tupperware_Development_3.mhtml", contract3 + "</body></html>"))

    # Continue with 7 more contracts of varying sizes...
    
    # Contract 4: Service Agreement (12 pages)
    contract4 = f"""<!DOCTYPE html>
<html>
<head><title>Professional Services Agreement</title></head>
<body>
<h1>PROFESSIONAL SERVICES AGREEMENT</h1>

<p>Agreement between {random.choice(companies)} and {random.choice(people)} Consulting LLC for environmental services at {random.choice(properties)} site in {random.choice(locations)}.</p>

<h2>SCOPE OF WORK</h2>
<p>Environmental assessment and remediation planning for the former {random.choice(properties)} manufacturing facility.</p>

<h2>SERVICE PROVIDER</h2>
<p>Company: {random.choice(people)} Environmental Consulting</p>
<p>Principal: {random.choice(people)}, P.E.</p>
<p>License: FL PE 12345</p>
<p>Address: 123 {random.choice(locations)} Avenue</p>

""" + "\\n\\n".join([f"<p>Task {i}: Environmental monitoring at {random.choice(properties)} location under supervision of {random.choice(people)}. Coordination with {random.choice(companies)} and {random.choice(locations)} regulatory authorities required.</p>" for i in range(1, 9)])

    contracts.append(("Environmental_Services_4.mhtml", contract4 + "</body></html>"))

    # Contract 5: Employment Agreement (8 pages)
    contract5 = f"""<!DOCTYPE html>
<html>
<head><title>Executive Employment Agreement</title></head>
<body>
<h1>EXECUTIVE EMPLOYMENT AGREEMENT</h1>

<p>Employment agreement between {random.choice(companies)} and {random.choice(people)} for the position of Regional Director, {random.choice(locations)} Operations.</p>

<h2>EMPLOYEE INFORMATION</h2>
<p>Name: {random.choice(people)}</p>
<p>SSN: 987-65-4321</p>
<p>Address: 456 {random.choice(properties)} Drive, {random.choice(locations)}, FL</p>
<p>Phone: (407) 555-7890</p>

<h2>POSITION DETAILS</h2>
<p>Title: Regional Director</p>
<p>Department: {random.choice(locations)} Operations</p>
<p>Supervisor: {random.choice(people)}, VP Operations</p>
<p>Base Salary: $185,000 annually</p>

""" + "\\n\\n".join([f"<p>Section {i}: Responsibilities include oversight of {random.choice(properties)} facility operations and coordination with {random.choice(people)} on {random.choice(locations)} regional initiatives.</p>" for i in range(1, 5)])

    contracts.append(("Executive_Employment_5.mhtml", contract5 + "</body></html>"))

    # Contract 6: Supply Agreement (30 pages)
    contract6 = f"""<!DOCTYPE html>
<html>
<head><title>Supply Chain Agreement</title></head>
<body>
<h1>SUPPLY CHAIN AGREEMENT</h1>

<p>Supply agreement between {random.choice(companies)} and {random.choice(properties)} Manufacturing Corp for production of containers at {random.choice(locations)} facility.</p>

<h2>SUPPLIER INFORMATION</h2>
<p>Supplier: {random.choice(properties)} Manufacturing Corp</p>
<p>Contact: {random.choice(people)}, Operations Manager</p>
<p>Facility: {random.choice(locations)} Production Center</p>
<p>Certification: ISO 9001:2015</p>

<h2>PRODUCT SPECIFICATIONS</h2>
<p>Primary products: Food storage containers for {random.choice(companies)}</p>
<p>Quality standards: Tupperware Global Standards</p>
<p>Testing facility: {random.choice(properties)} Quality Lab</p>

""" + "\\n\\n".join([f"<h3>Production Schedule {i}</h3><p>Monthly production targets for {random.choice(properties)} product line. Quality oversight by {random.choice(people)} with final approval from {random.choice(people)} at {random.choice(companies)}. All shipments to {random.choice(locations)} distribution center managed by {random.choice(people)}.</p>" for i in range(1, 25)])

    contracts.append(("Supply_Chain_Agreement_6.mhtml", contract6 + "</body></html>"))

    # Contract 7: Joint Venture (35 pages)
    contract7 = f"""<!DOCTYPE html>
<html>
<head><title>Joint Venture Agreement</title></head>
<body>
<h1>JOINT VENTURE AGREEMENT</h1>
<h2>{random.choice(properties).upper()} DEVELOPMENT JOINT VENTURE</h2>

<p>Joint venture between {random.choice(companies)} and {random.choice(properties)} Development Partners for the {random.choice(locations)} mixed-use project.</p>

<h2>VENTURE PARTNERS</h2>
<p>Lead Partner: {random.choice(companies)}</p>
<p>Development Partner: {random.choice(properties)} Development Partners</p>
<p>Managing Partner: {random.choice(people)}</p>
<p>Financial Partner: {random.choice(people)} Investment Group</p>

<h2>PROJECT SCOPE</h2>
<p>Development of {random.choice(properties)} Town Center in {random.choice(locations)}</p>
<p>Total investment: $150,000,000</p>
<p>Timeline: 5 years</p>

""" + "\\n\\n".join([f"<h3>Development Phase {i}</h3><p>Construction of {random.choice(properties)} component under direction of {random.choice(people)}. Environmental compliance managed by {random.choice(people)} with {random.choice(locations)} County oversight. {random.choice(companies)} provides funding and operational expertise for this phase.</p>" for i in range(1, 28)])

    contracts.append(("Joint_Venture_7.mhtml", contract7 + "</body></html>"))

    # Contract 8: Licensing Agreement (18 pages)
    contract8 = f"""<!DOCTYPE html>
<html>
<head><title>Technology Licensing Agreement</title></head>
<body>
<h1>TECHNOLOGY LICENSING AGREEMENT</h1>

<p>Licensing agreement between {random.choice(companies)} and {random.choice(properties)} Technologies for manufacturing processes at {random.choice(locations)} facility.</p>

<h2>LICENSOR</h2>
<p>Company: {random.choice(properties)} Technologies Inc.</p>
<p>Principal: {random.choice(people)}, CTO</p>
<p>Address: {random.choice(locations)} Tech Park</p>

<h2>LICENSED TECHNOLOGY</h2>
<p>Advanced polymer molding processes</p>
<p>Quality control systems</p>
<p>Environmental monitoring technology</p>

""" + "\\n\\n".join([f"<p>License Term {i}: Implementation of {random.choice(properties)} technology at {random.choice(companies)} facilities. Technical support provided by {random.choice(people)} with oversight from {random.choice(people)}. All installations in {random.choice(locations)} region coordinated through this agreement.</p>" for i in range(1, 14)])

    contracts.append(("Technology_License_8.mhtml", contract8 + "</body></html>"))

    # Contract 9: Acquisition Agreement (45 pages)
    contract9 = f"""<!DOCTYPE html>
<html>
<head><title>Asset Acquisition Agreement</title></head>
<body>
<h1>ASSET ACQUISITION AGREEMENT</h1>

<p>Acquisition of {random.choice(properties)} Holdings by {random.choice(companies)} including all {random.choice(locations)} County properties and operations.</p>

<h2>ACQUISITION DETAILS</h2>
<p>Purchase Price: $75,000,000</p>
<p>Closing Date: December 31, 2024</p>
<p>Due Diligence Period: 90 days</p>

<h2>SELLER INFORMATION</h2>
<p>Entity: {random.choice(properties)} Holdings LLC</p>
<p>Principal: {random.choice(people)}</p>
<p>Legal Counsel: {random.choice(people)}, Esq.</p>

<h2>ASSETS INCLUDED</h2>
<p>Real estate: 15 properties in {random.choice(locations)} County</p>
<p>Equipment: Manufacturing and office equipment</p>
<p>Intellectual property: {random.choice(properties)} brand and trademarks</p>

""" + "\\n\\n".join([f"<h3>Asset Category {i}</h3><p>Detailed inventory of {random.choice(properties)} assets being acquired by {random.choice(companies)}. Valuation performed by {random.choice(people)} & Associates. Environmental assessments by {random.choice(people)} Environmental. All {random.choice(locations)} properties inspected and approved. Transfer coordination managed by {random.choice(people)} with legal oversight from {random.choice(people)}.</p>" for i in range(1, 35)])

    contracts.append(("Asset_Acquisition_9.mhtml", contract9 + "</body></html>"))

    # Contract 10: Construction Agreement (22 pages)
    contract10 = f"""<!DOCTYPE html>
<html>
<head><title>Construction Agreement</title></head>
<body>
<h1>CONSTRUCTION AGREEMENT</h1>

<p>Construction of new {random.choice(companies)} distribution center at {random.choice(properties)} Industrial Park, {random.choice(locations)} County.</p>

<h2>CONTRACTOR</h2>
<p>General Contractor: {random.choice(people)} Construction LLC</p>
<p>Project Manager: {random.choice(people)}</p>
<p>License: CGC1234567</p>

<h2>PROJECT DETAILS</h2>
<p>Facility: 200,000 sq ft distribution center</p>
<p>Location: {random.choice(properties)} Industrial Park</p>
<p>Contract Value: $25,000,000</p>
<p>Completion: 18 months</p>

<h2>OWNER</h2>
<p>Owner: {random.choice(companies)}</p>
<p>Representative: {random.choice(people)}, Facilities Director</p>

""" + "\\n\\n".join([f"<h3>Construction Phase {i}</h3><p>Phase {i} construction activities for the {random.choice(properties)} distribution center. Supervision by {random.choice(people)} with quality control by {random.choice(people)}. All work must comply with {random.choice(locations)} County building codes. Environmental monitoring by {random.choice(people)} throughout construction.</p>" for i in range(1, 17)])

    contracts.append(("Construction_Agreement_10.mhtml", contract10 + "</body></html>"))

    # Save all contracts
    contracts_dir = Path('/mnt/c/seedJura/contracts')
    
    for filename, content in contracts:
        filepath = contracts_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created: {filename}")
    
    print(f"\nCreated 10 fake contracts with varying sizes:")
    print(f"- Short contracts (8-15 pages): 3 contracts")
    print(f"- Medium contracts (18-30 pages): 4 contracts") 
    print(f"- Large contracts (35-45 pages): 3 contracts")
    print(f"\nAll contracts feature Tupperware/Osceola entities with overlapping PII")
    print(f"Perfect for testing the learn-then-apply optimization!")

if __name__ == "__main__":
    create_fake_contracts()
