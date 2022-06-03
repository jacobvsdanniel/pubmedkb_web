function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
        "case_sensitive": document.getElementById("ta_case_sensitive").value,
        "max_length_diff": document.getElementById("ta_max_length_diff").value,
        "min_similarity": document.getElementById("ta_min_similarity").value,
        "max_names": document.getElementById("ta_max_names").value,
        "max_aliases": document.getElementById("ta_max_aliases").value,
    };

    fetch("./run_nen", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}
