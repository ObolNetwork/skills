#!/usr/bin/env python3
"""HubSpot CRM operations.

Provides search, read, and update operations for HubSpot CRM objects.
Uses the token from auth.py for authentication.

Usage:
    python3 crm.py search-contacts [--query QUERY] [--limit N] [--properties p1,p2]
    python3 crm.py get-contact ID [--properties p1,p2]
    python3 crm.py update-contact ID --property KEY --value VALUE
    python3 crm.py list-companies [--limit N] [--properties p1,p2]
    python3 crm.py get-company ID [--properties p1,p2]
    python3 crm.py update-company ID --property KEY --value VALUE
    python3 crm.py search-companies [--query QUERY] [--limit N]
    python3 crm.py get-contact-companies CONTACT_ID
    python3 crm.py get-contact-notes CONTACT_ID [--limit N]
    python3 crm.py get-contact-deals CONTACT_ID [--limit N]
    python3 crm.py get-company-notes COMPANY_ID [--limit N]
    python3 crm.py create-note (--body BODY | --body-file FILE) [--company ID] [--contact ID] [--deal ID] [--timestamp ISO8601]
    python3 crm.py update-note NOTE_ID [--body BODY | --body-file FILE] [--timestamp ISO8601]
    python3 crm.py list-properties OBJECT_TYPE [--custom-only]
    python3 crm.py export-contacts [--properties p1,p2] [--output FILE]
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse

from auth import get_token

BASE_URL = "https://api.hubapi.com"

DEFAULT_CONTACT_PROPS = [
    "firstname", "lastname", "email", "company", "jobtitle",
    "hs_lead_status", "lifecyclestage",
    "investor_advisor", "tags",
]

DEFAULT_COMPANY_PROPS = [
    "name", "domain", "industry", "description", "type",
    "numberofemployees", "city", "country",
]


def api_request(method, path, data=None, params=None):
    token = get_token()
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def search_contacts(query=None, limit=20, properties=None):
    props = properties or DEFAULT_CONTACT_PROPS
    body = {
        "limit": limit,
        "properties": props,
    }
    if query:
        body["query"] = query

    result = api_request("POST", "/crm/v3/objects/contacts/search", data=body)
    print(json.dumps(result, indent=2))


def get_contact(contact_id, properties=None):
    props = properties or DEFAULT_CONTACT_PROPS
    params = {"properties": ",".join(props)}
    result = api_request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)
    print(json.dumps(result, indent=2))


def update_contact(contact_id, prop, value):
    data = {"properties": {prop: value}}
    result = api_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", data=data)
    print(json.dumps(result, indent=2))


def list_companies(limit=20, properties=None):
    props = properties or DEFAULT_COMPANY_PROPS
    params = {"limit": limit, "properties": ",".join(props)}
    result = api_request("GET", "/crm/v3/objects/companies", params=params)
    print(json.dumps(result, indent=2))


def search_companies(query=None, limit=20, properties=None):
    props = properties or DEFAULT_COMPANY_PROPS
    body = {"limit": limit, "properties": props}
    if query:
        body["query"] = query
    result = api_request("POST", "/crm/v3/objects/companies/search", data=body)
    print(json.dumps(result, indent=2))


def get_company(company_id, properties=None):
    props = properties or DEFAULT_COMPANY_PROPS
    params = {"properties": ",".join(props)}
    result = api_request("GET", f"/crm/v3/objects/companies/{company_id}", params=params)
    print(json.dumps(result, indent=2))


def get_contact_associations(contact_id, to_object, limit=20):
    result = api_request("GET", f"/crm/v3/objects/contacts/{contact_id}/associations/{to_object}",
                         params={"limit": limit})
    return result


def get_contact_companies(contact_id):
    assoc = get_contact_associations(contact_id, "companies")
    company_ids = [r["id"] for r in assoc.get("results", [])]
    if not company_ids:
        print(json.dumps({"companies": []}))
        return

    companies = []
    for cid in company_ids:
        props = ",".join(DEFAULT_COMPANY_PROPS)
        company = api_request("GET", f"/crm/v3/objects/companies/{cid}",
                              params={"properties": props})
        companies.append(company)
    print(json.dumps({"companies": companies}, indent=2))


def get_contact_notes(contact_id, limit=10):
    assoc = get_contact_associations(contact_id, "notes")
    note_ids = [r["id"] for r in assoc.get("results", [])][:limit]
    if not note_ids:
        print(json.dumps({"notes": []}))
        return

    notes = []
    for nid in note_ids:
        note = api_request("GET", f"/crm/v3/objects/notes/{nid}",
                           params={"properties": "hs_note_body,hs_timestamp"})
        notes.append(note)
    print(json.dumps({"notes": notes}, indent=2))


def get_company_notes(company_id, limit=10):
    assoc = api_request("GET", f"/crm/v3/objects/companies/{company_id}/associations/notes",
                        params={"limit": limit})
    note_ids = [r["id"] for r in assoc.get("results", [])][:limit]
    if not note_ids:
        print(json.dumps({"notes": []}))
        return

    notes = []
    for nid in note_ids:
        note = api_request("GET", f"/crm/v3/objects/notes/{nid}",
                           params={"properties": "hs_note_body,hs_timestamp"})
        notes.append(note)
    print(json.dumps({"notes": notes}, indent=2))


def update_company(company_id, prop, value):
    data = {"properties": {prop: value}}
    result = api_request("PATCH", f"/crm/v3/objects/companies/{company_id}", data=data)
    print(json.dumps(result, indent=2))


# HubSpot-defined association type IDs for notes
NOTE_ASSOCIATION_TYPES = {
    "contact": 202,
    "company": 190,
    "deal": 214,
    "ticket": 228,
}


def create_note(body, company_id=None, contact_id=None, deal_id=None, timestamp=None):
    import datetime
    ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

    associations = []
    for kind, oid in (("company", company_id), ("contact", contact_id), ("deal", deal_id)):
        if oid:
            associations.append({
                "to": {"id": oid},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": NOTE_ASSOCIATION_TYPES[kind],
                }],
            })

    data = {
        "properties": {"hs_timestamp": ts, "hs_note_body": body},
    }
    if associations:
        data["associations"] = associations

    result = api_request("POST", "/crm/v3/objects/notes", data=data)
    print(json.dumps(result, indent=2))


def update_note(note_id, body=None, timestamp=None):
    properties = {}
    if body is not None:
        properties["hs_note_body"] = body
    if timestamp is not None:
        properties["hs_timestamp"] = timestamp
    if not properties:
        print("Nothing to update: provide --body/--body-file or --timestamp.", file=sys.stderr)
        sys.exit(1)

    result = api_request("PATCH", f"/crm/v3/objects/notes/{note_id}", data={"properties": properties})
    print(json.dumps(result, indent=2))


def get_contact_deals(contact_id, limit=10):
    assoc = get_contact_associations(contact_id, "deals")
    deal_ids = [r["id"] for r in assoc.get("results", [])][:limit]
    if not deal_ids:
        print(json.dumps({"deals": []}))
        return

    deal_props = "dealname,dealstage,amount,pipeline,closedate,description"
    deals = []
    for did in deal_ids:
        deal = api_request("GET", f"/crm/v3/objects/deals/{did}",
                           params={"properties": deal_props})
        deals.append(deal)
    print(json.dumps({"deals": deals}, indent=2))


def list_properties(object_type, custom_only=False):
    result = api_request("GET", f"/crm/v3/properties/{object_type}")
    props = result.get("results", [])
    if custom_only:
        props = [p for p in props
                 if not p["name"].startswith("hs_") and not p.get("hubspotDefined")]
    output = [{"name": p["name"], "label": p["label"], "type": p["type"],
               "fieldType": p.get("fieldType"), "description": p.get("description", "")}
              for p in props]
    print(json.dumps(output, indent=2))


def export_contacts(properties=None, output_file=None):
    props = properties or DEFAULT_CONTACT_PROPS
    all_contacts = []
    after = None

    while True:
        params = {"limit": 100, "properties": ",".join(props)}
        if after:
            params["after"] = after

        result = api_request("GET", "/crm/v3/objects/contacts", params=params)
        contacts = result.get("results", [])
        all_contacts.extend(contacts)

        paging = result.get("paging", {}).get("next", {})
        after = paging.get("after")
        if not after:
            break

        print(f"Fetched {len(all_contacts)} contacts...", file=sys.stderr)

    # Flatten to CSV-friendly format
    rows = []
    for c in all_contacts:
        row = {"id": c["id"]}
        row.update(c.get("properties", {}))
        rows.append(row)

    if output_file:
        with open(output_file, "w") as f:
            if rows:
                headers = list(rows[0].keys())
                f.write(",".join(headers) + "\n")
                for row in rows:
                    f.write(",".join(str(row.get(h, "")).replace(",", ";") for h in headers) + "\n")
        print(f"Exported {len(rows)} contacts to {output_file}", file=sys.stderr)
    else:
        print(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description="HubSpot CRM operations")
    sub = parser.add_subparsers(dest="command")

    # search-contacts
    p = sub.add_parser("search-contacts")
    p.add_argument("--query", "-q")
    p.add_argument("--limit", "-l", type=int, default=20)
    p.add_argument("--properties", "-p")

    # get-contact
    p = sub.add_parser("get-contact")
    p.add_argument("id")
    p.add_argument("--properties", "-p")

    # update-contact
    p = sub.add_parser("update-contact")
    p.add_argument("id")
    p.add_argument("--property", required=True)
    p.add_argument("--value", required=True)

    # list-companies
    p = sub.add_parser("list-companies")
    p.add_argument("--limit", "-l", type=int, default=20)
    p.add_argument("--properties", "-p")

    # search-companies
    p = sub.add_parser("search-companies")
    p.add_argument("--query", "-q")
    p.add_argument("--limit", "-l", type=int, default=20)

    # get-company
    p = sub.add_parser("get-company")
    p.add_argument("id")
    p.add_argument("--properties", "-p")

    # get-contact-companies
    p = sub.add_parser("get-contact-companies")
    p.add_argument("id")

    # get-contact-notes
    p = sub.add_parser("get-contact-notes")
    p.add_argument("id")
    p.add_argument("--limit", "-l", type=int, default=10)

    # get-contact-deals
    p = sub.add_parser("get-contact-deals")
    p.add_argument("id")
    p.add_argument("--limit", "-l", type=int, default=10)

    # get-company-notes
    p = sub.add_parser("get-company-notes")
    p.add_argument("id")
    p.add_argument("--limit", "-l", type=int, default=10)

    # update-company
    p = sub.add_parser("update-company")
    p.add_argument("id")
    p.add_argument("--property", required=True)
    p.add_argument("--value", required=True)

    # create-note
    p = sub.add_parser("create-note")
    body_group = p.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="Note body (HTML allowed)")
    body_group.add_argument("--body-file", help="Read note body from file")
    p.add_argument("--company", help="Company ID to associate")
    p.add_argument("--contact", help="Contact ID to associate")
    p.add_argument("--deal", help="Deal ID to associate")
    p.add_argument("--timestamp", help="ISO 8601 timestamp (defaults to now)")

    # update-note
    p = sub.add_parser("update-note")
    p.add_argument("id")
    body_group = p.add_mutually_exclusive_group()
    body_group.add_argument("--body", help="New note body (HTML allowed)")
    body_group.add_argument("--body-file", help="Read new note body from file")
    p.add_argument("--timestamp", help="ISO 8601 timestamp")

    # list-properties
    p = sub.add_parser("list-properties")
    p.add_argument("object_type")
    p.add_argument("--custom-only", action="store_true")

    # export-contacts
    p = sub.add_parser("export-contacts")
    p.add_argument("--properties", "-p")
    p.add_argument("--output", "-o")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    props = args.properties.split(",") if hasattr(args, "properties") and args.properties else None

    if args.command == "search-contacts":
        search_contacts(args.query, args.limit, props)
    elif args.command == "get-contact":
        get_contact(args.id, props)
    elif args.command == "update-contact":
        update_contact(args.id, args.property, args.value)
    elif args.command == "list-companies":
        list_companies(args.limit, props)
    elif args.command == "search-companies":
        search_companies(getattr(args, "query", None), args.limit, props)
    elif args.command == "get-company":
        get_company(args.id, props)
    elif args.command == "get-contact-companies":
        get_contact_companies(args.id)
    elif args.command == "get-contact-notes":
        get_contact_notes(args.id, args.limit)
    elif args.command == "get-contact-deals":
        get_contact_deals(args.id, args.limit)
    elif args.command == "get-company-notes":
        get_company_notes(args.id, args.limit)
    elif args.command == "update-company":
        update_company(args.id, args.property, args.value)
    elif args.command == "create-note":
        body = args.body
        if args.body_file:
            with open(args.body_file) as f:
                body = f.read()
        create_note(body, args.company, args.contact, args.deal, args.timestamp)
    elif args.command == "update-note":
        body = args.body
        if args.body_file:
            with open(args.body_file) as f:
                body = f.read()
        update_note(args.id, body, args.timestamp)
    elif args.command == "list-properties":
        list_properties(args.object_type, args.custom_only)
    elif args.command == "export-contacts":
        export_contacts(props, getattr(args, "output", None))


if __name__ == "__main__":
    main()
