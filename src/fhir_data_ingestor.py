#!/usr/bin/env python3  
"""Bulk import FHIR NDJSON files into MongoDB"""  
  
import json  
from pathlib import Path  
from pymongo import MongoClient, InsertOne  
from pymongo.errors import BulkWriteError  
from tqdm import tqdm  
  
def bulk_import(uri: str, database: str, collection: str, data_dir: str):  
    client = MongoClient(uri)  
    db = client[database]  
    coll = db[collection]  
      
    # Create indexes first  
    print("Creating indexes...")  
    coll.create_index([("resourceType", 1), ("id", 1)])  
    coll.create_index([("subject.reference", 1)])  
    coll.create_index([("patient.reference", 1)])  
    coll.create_index([("encounter.reference", 1)])  
      
    # Import all NDJSON files  
    data_path = Path(data_dir)  
    total_inserted = 0  
      
    for ndjson_file in sorted(data_path.glob("*.ndjson")):  
        print(f"\nImporting {ndjson_file.name}...")  
          
        with open(ndjson_file, 'r') as f:  
            batch = []  
            for line in tqdm(f, desc="Reading"):  
                resource = json.loads(line)  
                # Use resourceType/id as _id for deduplication  
                resource["_id"] = f"{resource['resourceType']}/{resource['id']}"  
                batch.append(InsertOne(resource))  
                  
                if len(batch) >= 5000:  
                    try:  
                        result = coll.bulk_write(batch, ordered=False)  
                        total_inserted += result.inserted_count  
                    except BulkWriteError as e:  
                        total_inserted += e.details.get('nInserted', 0)  
                    batch = []  
              
            # Final batch  
            if batch:  
                try:  
                    result = coll.bulk_write(batch, ordered=False)  
                    total_inserted += result.inserted_count  
                except BulkWriteError as e:  
                    total_inserted += e.details.get('nInserted', 0)  
      
    print(f"\n✓ Total resources imported: {total_inserted:,}")  
  
if __name__ == "__main__":  
    bulk_import(  
        uri="mongodb://localhost:27017",  
        database="fhir_poc",  
        collection="resources",  
        data_dir="./fhir_data"  
    )  
