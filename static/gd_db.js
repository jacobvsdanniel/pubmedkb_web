function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "type": document.getElementById("sl_type").value,
        "gene_id": document.getElementById("ta_gene_id").value,
        "disease_id": document.getElementById("ta_disease_id").value,
        "top_k": document.getElementById("ta_top_k").value,
    };

    fetch("./run_gd_db", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    type = document.getElementById("sl_type").value;
    gene_id = document.getElementById("ta_gene_id").value;
    disease_id = document.getElementById("ta_disease_id").value;
    top_k = document.getElementById("ta_top_k").value;

    type = encodeURIComponent(type)
    gene_id = encodeURIComponent(gene_id)
    disease_id = encodeURIComponent(disease_id)
    top_k = encodeURIComponent(top_k)

    url = `./query_gd_db`
    url = `${url}?type=${type}`
    url = `${url}&gene_id=${gene_id}`
    url = `${url}&disease_id=${disease_id}`
    url = `${url}&top_k=${top_k}`

    window.open(url, "_blank");
}
