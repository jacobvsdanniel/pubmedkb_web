function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
    };

    fetch("./run_qa", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    query = document.getElementById("ta_query").value;
    query = encodeURIComponent(query)
    url = `./query_qa?query=${query}`
    window.open(url, "_blank");
}

function post_json(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
    };

    fetch("./query_qa", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}
