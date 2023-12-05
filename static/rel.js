function get_entity_spec(filter, _type, _id, name) {
    if (filter == "type_id") {
        query = ["type_id", [_type, _id]]
    } else if (filter == "type_name") {
        query = ["type_name", [_type, name]]
    } else if (filter == "type_id_name") {
        query = ["AND", [["type_id", [_type, _id]], ["type_name", [_type, name]]]]
    }
    query = JSON.stringify(query)
    return query
}


function get_query_spec() {
    e1_filter = document.getElementById("sl_e1_filter").value
    e1_type = document.getElementById("sl_e1_type").value
    e1_id = document.getElementById("ta_e1_id").value
    e1_name = document.getElementById("ta_e1_name").value

    e2_filter = document.getElementById("sl_e2_filter").value
    e2_type = document.getElementById("sl_e2_type").value
    e2_id = document.getElementById("ta_e2_id").value
    e2_name = document.getElementById("ta_e2_name").value

    pmid = document.getElementById("ta_query_pmid").value

    query_filter = document.getElementById("sl_query_filter").value

    if (query_filter == "P") {
        e1_spec = ""
        e2_spec = ""

    } else if (query_filter == "A") {
        e1_spec = get_entity_spec(e1_filter, e1_type, e1_id, e1_name)
        e2_spec = ""
        pmid = ""

    } else if (query_filter == "B") {
        e1_spec = ""
        e2_spec = get_entity_spec(e2_filter, e2_type, e2_id, e2_name)
        pmid = ""

    } else if (query_filter == "AB") {
        e1_spec = get_entity_spec(e1_filter, e1_type, e1_id, e1_name)
        e2_spec = get_entity_spec(e2_filter, e2_type, e2_id, e2_name)
        pmid = ""

    } else if (query_filter == "ABP") {
        e1_spec = get_entity_spec(e1_filter, e1_type, e1_id, e1_name)
        e2_spec = get_entity_spec(e2_filter, e2_type, e2_id, e2_name)
    }

    query_spec = [e1_spec, e2_spec, pmid]
    return query_spec
}


function run_query() {
    document.getElementById("div_status").innerHTML = "Loading...";

    query_spec = get_query_spec()
    e1_spec = query_spec[0]
    e2_spec = query_spec[1]
    pmid = query_spec[2]

    request_data = {
        "e1_spec": e1_spec,
        "e2_spec": e2_spec,
        "pmid": pmid,
        "paper_start": document.getElementById("ta_paper_start").value,
        "paper_end": document.getElementById("ta_paper_end").value,
        "paper_sort": document.getElementById("sl_paper_sort").value,
    }

    fetch("./run_rel", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}


function get_json() {
    query_spec = get_query_spec()
    e1_spec = query_spec[0]
    e2_spec = query_spec[1]
    pmid = query_spec[2]

    paper_start = document.getElementById("ta_paper_start").value
    paper_end = document.getElementById("ta_paper_end").value
    paper_sort = document.getElementById("sl_paper_sort").value

    e1_spec = encodeURIComponent(e1_spec)
    e2_spec = encodeURIComponent(e2_spec)
    pmid = encodeURIComponent(pmid)

    paper_start = encodeURIComponent(paper_start)
    paper_end = encodeURIComponent(paper_end)
    paper_sort = encodeURIComponent(paper_sort)

    url = `./query_rel`
    url = `${url}?e1_spec=${e1_spec}`
    url = `${url}&e2_spec=${e2_spec}`
    url = `${url}&pmid=${pmid}`
    url = `${url}&paper_start=${paper_start}`
    url = `${url}&paper_end=${paper_end}`
    url = `${url}&paper_sort=${paper_sort}`

    window.open(url, "_blank");
}


function post_json() {
    document.getElementById("div_status").innerHTML = "Loading...";

    query_spec = get_query_spec()
    e1_spec = query_spec[0]
    e2_spec = query_spec[1]
    pmid = query_spec[2]

    request_data = {
        "e1_spec": e1_spec,
        "e2_spec": e2_spec,
        "pmid": pmid,
        "paper_start": document.getElementById("ta_paper_start").value,
        "paper_end": document.getElementById("ta_paper_end").value,
        "paper_sort": document.getElementById("sl_paper_sort").value,
    }

    fetch("./query_rel", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}


function get_statistics_json() {
    query_spec = get_query_spec()
    e1_spec = query_spec[0]
    e2_spec = query_spec[1]
    pmid = query_spec[2]

    e1_spec = encodeURIComponent(e1_spec)
    e2_spec = encodeURIComponent(e2_spec)
    pmid = encodeURIComponent(pmid)

    url = `./query_rel_statistics`
    url = `${url}?e1_spec=${e1_spec}`
    url = `${url}&e2_spec=${e2_spec}`
    url = `${url}&pmid=${pmid}`

    window.open(url, "_blank");
}


function post_statistics_json() {
    document.getElementById("div_status").innerHTML = "Loading...";

    query_spec = get_query_spec()
    e1_spec = query_spec[0]
    e2_spec = query_spec[1]
    pmid = query_spec[2]

    request_data = {
        "e1_spec": e1_spec,
        "e2_spec": e2_spec,
        "pmid": pmid,
    }

    fetch("./query_rel_statistics", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}
