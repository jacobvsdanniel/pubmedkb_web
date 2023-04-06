function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
    };

    fetch("./run_paper", {method: "post", body: JSON.stringify(request_data)})
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
    query = encodeURI(query)
    url = `./query_paper?query=${query}`
    window.open(url, "_blank");
}
