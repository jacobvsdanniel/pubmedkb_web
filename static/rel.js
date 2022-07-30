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

        "query_filter": document.getElementById("sl_query_filter").value,
        "query_rels": document.getElementById("ta_query_rels").value,
        "query_pmid": document.getElementById("ta_query_pmid").value,
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

function run_query_summary(){
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

        "query_filter": document.getElementById("sl_query_filter").value,
        "query_rels": document.getElementById("ta_query_rels").value,
        "query_pmid": document.getElementById("ta_query_pmid").value,
    };

    fetch("./run_rel_summary", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}
