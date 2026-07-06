from fastapi import HTTPException
import asyncio


async def upload_xml(
    client,
    dpsim_url: str,
    zip_path: str,
    filename: str = "Crete_2030.zip",
    fallback_keyword: str = "2030",
) -> str:
    with open(zip_path, "rb") as f:
        files = {"file": (filename, f, "application/zip")}
        xml_res = await client.post(f"{dpsim_url}/xml", files=files)

    if xml_res.status_code == 200:
        body = xml_res.json()
        print(f"[DEBUG] xml_upload_response_body={body}")
        keyword = body.get(fallback_keyword) or body.get("keyword") or fallback_keyword
        print(f"[DEBUG] xml_keyword_resolved={keyword!r} (fallback={fallback_keyword!r})")
        return keyword

    if "File exists" in xml_res.text:
        print(f"[DEBUG] xml_upload_file_exists fallback_keyword={fallback_keyword!r}")
        return fallback_keyword

    raise HTTPException(
        status_code=xml_res.status_code,
        detail=f"Step 1 Failed (XML Upload): {xml_res.text}",
    )


async def upload_profile(client, dpsim_url: str, profile_keyword: str, payload: list[dict]) -> dict:
    prof_res = await client.post(
        f"{dpsim_url}/jts/profile/{profile_keyword}",
        json=payload,
    )

    try:
        prof_body = prof_res.json()
    except Exception:
        prof_body = {"raw": prof_res.text}

    if prof_res.status_code != 200:
        raise HTTPException(
            status_code=prof_res.status_code,
            detail={
                "error": "Step 2 Failed (Profile Upload)",
                "response": prof_body,
                "payload_count": len(payload),
                "sample_payload": payload[:5],
            },
        )

    return prof_body


async def start_simulation(client, dpsim_url: str, sim_payload: dict):
    sim_res = await client.post(f"{dpsim_url}/s", json=sim_payload)

    print("[DEBUG] sim_start_status=", sim_res.status_code)
    print("[DEBUG] sim_start_body=", sim_res.text)

    if sim_res.status_code != 200:
        raise HTTPException(
            status_code=sim_res.status_code,
            detail=f"Failed to start simulation: {sim_res.text}",
        )

    try:
        return sim_res.json()
    except Exception:
        return {"raw": sim_res.text}


async def poll_result(
    client,
    dpsim_url: str,
    sim_name: str,
    max_retries: int = 20,
    delay_seconds: float = 2.0,
) -> dict:
    for attempt in range(max_retries):
        await asyncio.sleep(delay_seconds)

        result_res = await client.get(f"{dpsim_url}/jts/result/{sim_name}")

        if result_res.status_code == 200:
            return result_res.json()

        if result_res.status_code == 404:
            print(
                f"[DEBUG] Result not ready yet. "
                f"Attempt {attempt + 1}/{max_retries}"
            )
            continue

        raise HTTPException(
            status_code=result_res.status_code,
            detail=f"Error fetching results: {result_res.text}",
        )

    raise HTTPException(
        status_code=408,
        detail="Simulation timed out while waiting for results.",
    )
