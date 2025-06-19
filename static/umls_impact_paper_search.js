function post_run(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./run_umls_impact_paper_search", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function post_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./query_umls_impact_paper_search", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_query(){
    query = document.getElementById("ta_query").value;
    query = encodeURIComponent(query)
    url = `./query_umls_impact_paper_search?query=${query}`
    window.open(url, "_blank");
}
