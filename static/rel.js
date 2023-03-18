function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "e1_filter": document.getElementById("sl_e1_filter").value,
        "e1_type": document.getElementById("sl_e1_type").value,
        "e1_id": document.getElementById("ta_e1_id").value,
        "e1_name": document.getElementById("ta_e1_name").value,

        "e2_filter": document.getElementById("sl_e2_filter").value,
        "e2_type": document.getElementById("sl_e2_type").value,
        "e2_id": document.getElementById("ta_e2_id").value,
        "e2_name": document.getElementById("ta_e2_name").value,

        "query_pmid": document.getElementById("ta_query_pmid").value,
        "query_filter": document.getElementById("sl_query_filter").value,

        "kb_start": document.getElementById("ta_kb_start").value,
        "kb_end": document.getElementById("ta_kb_end").value,
        "paper_start": document.getElementById("ta_paper_start").value,
        "paper_end": document.getElementById("ta_paper_end").value,
        "paper_sort": document.getElementById("sl_paper_sort").value,
    };

    fetch("./run_rel", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    e1_filter = document.getElementById("sl_e1_filter").value,
    e1_type = document.getElementById("sl_e1_type").value,
    e1_id = document.getElementById("ta_e1_id").value,
    e1_name = document.getElementById("ta_e1_name").value,
    e2_filter = document.getElementById("sl_e2_filter").value,
    e2_type = document.getElementById("sl_e2_type").value,
    e2_id = document.getElementById("ta_e2_id").value,
    e2_name = document.getElementById("ta_e2_name").value,
    query_pmid = document.getElementById("ta_query_pmid").value,
    query_filter = document.getElementById("sl_query_filter").value,
    kb_start = document.getElementById("ta_kb_start").value,
    kb_end = document.getElementById("ta_kb_end").value,
    paper_start = document.getElementById("ta_paper_start").value,
    paper_end = document.getElementById("ta_paper_end").value,
    paper_sort = document.getElementById("sl_paper_sort").value,

    e1_filter = encodeURI(e1_filter)
    e1_type = encodeURI(e1_type)
    e1_id = encodeURI(e1_id)
    e1_name = encodeURI(e1_name)
    e2_filter = encodeURI(e2_filter)
    e2_type = encodeURI(e2_type)
    e2_id = encodeURI(e2_id)
    e2_name = encodeURI(e2_name)
    query_pmid = encodeURI(query_pmid)
    query_filter = encodeURI(query_filter)
    kb_start = encodeURI(kb_start)
    kb_end = encodeURI(kb_end)
    paper_start = encodeURI(paper_start)
    paper_end = encodeURI(paper_end)
    paper_sort = encodeURI(paper_sort)

    url = `./query_rel`
    url = `${url}?e1_filter=${e1_filter}`
    url = `${url}&e1_type=${e1_type}`
    url = `${url}&e1_id=${e1_id}`
    url = `${url}&e1_name=${e1_name}`
    url = `${url}&e2_filter=${e2_filter}`
    url = `${url}&e2_type=${e2_type}`
    url = `${url}&e2_id=${e2_id}`
    url = `${url}&e2_name=${e2_name}`
    url = `${url}&query_pmid=${query_pmid}`
    url = `${url}&query_filter=${query_filter}`
    url = `${url}&kb_start=${kb_start}`
    url = `${url}&kb_end=${kb_end}`
    url = `${url}&paper_start=${paper_start}`
    url = `${url}&paper_end=${paper_end}`
    url = `${url}&paper_sort=${paper_sort}`

    window.open(url, "_blank");
}

function get_statistics_json(){
    e1_filter = document.getElementById("sl_e1_filter").value,
    e1_type = document.getElementById("sl_e1_type").value,
    e1_id = document.getElementById("ta_e1_id").value,
    e1_name = document.getElementById("ta_e1_name").value,
    e2_filter = document.getElementById("sl_e2_filter").value,
    e2_type = document.getElementById("sl_e2_type").value,
    e2_id = document.getElementById("ta_e2_id").value,
    e2_name = document.getElementById("ta_e2_name").value,
    query_pmid = document.getElementById("ta_query_pmid").value,
    query_filter = document.getElementById("sl_query_filter").value,
    kb_start = document.getElementById("ta_kb_start").value,
    kb_end = document.getElementById("ta_kb_end").value,
    paper_start = document.getElementById("ta_paper_start").value,
    paper_end = document.getElementById("ta_paper_end").value,
    paper_sort = document.getElementById("sl_paper_sort").value,

    e1_filter = encodeURI(e1_filter)
    e1_type = encodeURI(e1_type)
    e1_id = encodeURI(e1_id)
    e1_name = encodeURI(e1_name)
    e2_filter = encodeURI(e2_filter)
    e2_type = encodeURI(e2_type)
    e2_id = encodeURI(e2_id)
    e2_name = encodeURI(e2_name)
    query_pmid = encodeURI(query_pmid)
    query_filter = encodeURI(query_filter)
    kb_start = encodeURI(kb_start)
    kb_end = encodeURI(kb_end)
    paper_start = encodeURI(paper_start)
    paper_end = encodeURI(paper_end)
    paper_sort = encodeURI(paper_sort)

    url = `./query_rel_statistics`
    url = `${url}?e1_filter=${e1_filter}`
    url = `${url}&e1_type=${e1_type}`
    url = `${url}&e1_id=${e1_id}`
    url = `${url}&e1_name=${e1_name}`
    url = `${url}&e2_filter=${e2_filter}`
    url = `${url}&e2_type=${e2_type}`
    url = `${url}&e2_id=${e2_id}`
    url = `${url}&e2_name=${e2_name}`
    url = `${url}&query_pmid=${query_pmid}`
    url = `${url}&query_filter=${query_filter}`
    url = `${url}&kb_start=${kb_start}`
    url = `${url}&kb_end=${kb_end}`
    url = `${url}&paper_start=${paper_start}`
    url = `${url}&paper_end=${paper_end}`
    url = `${url}&paper_sort=${paper_sort}`

    window.open(url, "_blank");
}
